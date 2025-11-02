#!/usr/bin/env python3

"""
Combined UltraSmooth Browser Video Server:
 - 60 FPS streaming screenshots
 - Full command history and terminal tracking
 - Continuous streaming with greenlet-safe command execution
 - Working STOP button
"""

import asyncio
import json
import os
import sys
import base64
import argparse
from pathlib import Path
import time
import threading
import queue
import concurrent.futures

try:
    from aiohttp import web
    import aiohttp_cors
except ImportError:
    print("Error: aiohttp required. Install with: pip install aiohttp aiohttp-cors")
    sys.exit(1)

# Import agent
sys.path.insert(0, str(Path(__file__).parent.parent))
try:
    from agent import LLMBrowserAgent
except ImportError as e:
    print(f"Error importing agent: {e}")
    print("Make sure agent.py is in the parent directory")
    sys.exit(1)


class CombinedVideoServer:
    """Continuous 60fps video + complete command/terminal tracking with working stop."""

    def __init__(self, host="0.0.0.0", port=8085, fps=60):  
        self.host = host
        self.port = port
        self.fps = fps
        self.frame_interval = 1.0 / self.fps

        self.app = web.Application()
        self.websockets = set()
        self.screenshot_queue = queue.Queue(maxsize=20)
        self.screenshot_enabled = threading.Event()
        self.shutdown_event = threading.Event()
        self.playwright_thread = None
        self.thread_running = False
        
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)

        self.agent = None
        self.agent_ready = threading.Event()
        self.init_queue = queue.Queue()
        self.init_response_queue = queue.Queue()
        self.task_queue = queue.Queue()
        self.task_response_queue = queue.Queue()
        
        self.playwright_command_queue = queue.Queue()

        # Task cancellation support
        self.task_state = None
        self.task_lock = threading.Lock()
        self.task_cancelled = threading.Event()  # NEW: For cancellation
        self.streaming_active = False
        self.screenshot_task = None

        self._setup_routes()
        self._setup_cors()

    def _setup_routes(self):
        """Setup routes for static files and WebSocket"""
        # Get the static directory (where HTML/CSS/JS files are)
        static_dir = Path(__file__).parent / 'static'
        
        # WebSocket endpoint
        self.app.router.add_get('/ws', self.websocket_handler)
        
        # Serve index.html at root
        self.app.router.add_get('/', self.serve_index)
        
        # Serve app.html
        self.app.router.add_get('/app', self.serve_app)
        
        # Serve all static files (CSS, JS)
        self.app.router.add_static('/static/', static_dir, name='static')
        
        # Also serve CSS and JS files directly from root for convenience
        self.app.router.add_get('/{filename:.+\\.css}', self.serve_static_file)
        self.app.router.add_get('/{filename:.+\\.js}', self.serve_static_file)

    async def serve_index(self, request):
        """Serve the landing page"""
        html_path = Path(__file__).parent / 'static' / 'index.html'
        if not html_path.exists():
            return web.Response(text="index.html not found", status=404)
        return web.FileResponse(html_path)

    async def serve_app(self, request):
        """Serve the main application page"""
        html_path = Path(__file__).parent / 'static' / 'app.html'
        if not html_path.exists():
            return web.Response(text="app.html not found", status=404)
        return web.FileResponse(html_path)

    async def serve_static_file(self, request):
        """Serve CSS and JS files"""
        filename = request.match_info['filename']
        file_path = Path(__file__).parent / 'static' / filename
        if not file_path.exists():
            return web.Response(text=f"{filename} not found", status=404)
        return web.FileResponse(file_path)

    def _setup_cors(self):
        cors = aiohttp_cors.setup(self.app, defaults={
            "*": aiohttp_cors.ResourceOptions(
                allow_credentials=True,
                expose_headers="*",
                allow_headers="*",
            )
        })
        for route in list(self.app.router.routes()):
            cors.add(route)

    async def websocket_handler(self, request):
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        self.websockets.add(ws)
        print(f" Client connected. Total: {len(self.websockets)}")

        await self.send_message(ws, {
            'type': 'status',
            'message': 'Connected',
            'ready': self.agent_ready.is_set()
        })

        try:
            async for msg in ws:
                if msg.type == web.WSMsgType.TEXT:
                    await self.handle_message(ws, msg.data)
                elif msg.type == web.WSMsgType.ERROR:
                    print(f'WebSocket error: {ws.exception()}')
        except Exception as e:
            print(f"WebSocket handler error: {e}")
        finally:
            self.websockets.discard(ws)
            print(f" Client disconnected. Total: {len(self.websockets)}")
        return ws

    async def handle_message(self, ws, data):
        try:
            message = json.loads(data)
            msg_type = message.get('type')
            print(f"Received: {msg_type}")
            
            if msg_type == 'execute_task':
                await self.execute_task(message.get('task', ''))
            elif msg_type == 'stop_task':
                await self.stop_task()
            elif msg_type == 'initialize':
                await self.initialize_agent(message.get('config', {}))
            elif msg_type == 'start_stream':
                await self.start_streaming()
            elif msg_type == 'stop_stream':
                await self.stop_streaming()
        except Exception as e:
            print(f"Error handling message: {e}")
            await self.send_message(ws, {'type': 'error', 'message': str(e)})

    def _playwright_thread_worker(self):
        """Worker thread that runs Playwright operations"""
        agent = None
        last_screenshot_time = 0
        print(" Playwright thread started")
        
        try:
            # Wait for initialization command
            print("â³ Waiting for init command...")
            command = self.init_queue.get(timeout=60)
            
            if command.get('type') == 'init':
                config = command.get('config', {})
                api_key = config.get('api_key') or os.getenv('GROQ_API_KEY')
                
                if not api_key:
                    raise ValueError("GROQ_API_KEY not found in config or environment")
                    
                model = config.get('model', 'llama-3.1-8b-instant')
                print(f" Initializing agent with model: {model}")
                
                agent = LLMBrowserAgent(api_key=api_key, headless=False, model=model)
                self.agent = agent
                self.agent_ready.set()
                self.init_response_queue.put({'type': 'init_success', 'model': agent.model})
                print(" Agent initialized successfully")
            else:
                self.init_response_queue.put({'type': 'init_error', 'error': 'Init timeout'})
                return

            # Main loop
            while self.thread_running and not self.shutdown_event.is_set():
                now = time.time()
                
                # Capture screenshots if enabled
                if self.screenshot_enabled.is_set() and agent and agent.browser:
                    if now - last_screenshot_time >= self.frame_interval:
                        try:
                            byteshot = agent.browser.page.screenshot(type='png')
                            if self.screenshot_queue.qsize() < 15:
                                self.screenshot_queue.put_nowait(byteshot)
                            last_screenshot_time = now
                        except Exception as e:
                            pass  # Silently ignore screenshot errors

                # Check for cancellation
                if self.task_cancelled.is_set():
                    with self.task_lock:
                        if self.task_state:
                            self.task_state = None
                            self.task_response_queue.put({'type': 'task_stopped'})
                            print(" Task cancelled by user")
                    self.task_cancelled.clear()

                # Process task state
                with self.task_lock:
                    if self.task_state:
                        self._step_task_state(agent)

                # Execute commands from queue
                try:
                    cmd_to_run = self.playwright_command_queue.get_nowait()
                    result = agent._execute_command(cmd_to_run)
                    with self.task_lock:
                        if self.task_state and self.task_state['state'] == 'awaiting_command_result':
                            self.task_state['result'] = result
                            self.task_state['state'] = 'process_command_result'
                except queue.Empty:
                    pass

                # Handle task queue
                try:
                    command = self.task_queue.get(timeout=0.001)
                    if command.get('type') == 'execute_task':
                        self._init_task_state(agent, command.get('task', ''))
                    elif command.get('type') == 'stop_task':
                        # Set cancellation flag
                        self.task_cancelled.set()
                except queue.Empty:
                    pass

                time.sleep(0.001)
                
        except Exception as e:
            print(f" Playwright thread error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            if agent:
                try:
                    agent.close()
                    print(" Agent closed")
                except:
                    pass
            print(" Playwright thread ended.")

    def _init_task_state(self, agent, task):
        """Initialize task execution state"""
        # Clear any previous cancellation
        self.task_cancelled.clear()
        
        agent.step_count = 0
        agent.conversation_history = []
        self.task_state = {
            'task': task,
            'state': 'prompt_llm',
            'future': None,
            'max_steps': agent.DEFAULT_MAX_STEPS,
            'commands': [],
            'terminal': []
        }
        self.task_response_queue.put({'type': 'task_start', 'task': task})

    def _step_task_state(self, agent):
        """Step through task execution state machine"""
        state = self.task_state
        if not state:
            return

        # Check for cancellation at each step
        if self.task_cancelled.is_set():
            return

        try:
            if state['state'] == 'awaiting_llm_response':
                future = state.get('future')
                if not future or not future.done():
                    return
                try:
                    state['llm_response'] = future.result()
                    state['future'] = None
                    state['state'] = 'parse_response'
                except Exception as e:
                    raise Exception(f"LLM call failed: {e}")

            elif state['state'] == 'awaiting_command_result':
                return

            if state['state'] == 'prompt_llm':
                prompt = f"Task: {state['task']}\n\nWhat is the FIRST single command?"
                state['future'] = self.executor.submit(agent._call_llm, prompt)
                state['state'] = 'awaiting_llm_response'
            
            elif state['state'] == 'parse_response':
                parsed = agent._parse_response(state['llm_response'])
                if 'error' in parsed:
                    self.task_response_queue.put({'type': 'parse_error', 'error': parsed['error']})
                    retry_prompt = f"Invalid format: {parsed['error']}. Retry."
                    state['future'] = self.executor.submit(agent._call_llm, retry_prompt)
                    state['state'] = 'awaiting_llm_response'
                    return

                if parsed.get('done'):
                    self.task_response_queue.put({
                        'type': 'task_completed',
                        'reasoning': parsed.get('thinking', ''),
                        'finish_message': parsed.get('finish_message', ''),
                        'command_history': state['commands'],
                    })
                    self.task_state = None
                    return
                
                if agent.step_count + 1 > state['max_steps']:
                    self.task_response_queue.put({'type': 'max_steps_reached'})
                    self.task_state = None
                    return
                
                state['parsed'] = parsed
                state['state'] = 'announce_step'

            elif state['state'] == 'announce_step':
                agent.step_count += 1
                parsed = state['parsed']
                cmd_entry = {
                    'step': agent.step_count,
                    'command': parsed['command'],
                    'thinking': parsed.get('thinking', '')
                }
                state['commands'].append(cmd_entry)
                
                # Create terminal message for this step only
                term_msg = f"\n--- Step {agent.step_count} ---\nThinking: {parsed.get('thinking', '')}\nCommand: {parsed['command']}\n"
                state['terminal'].append(term_msg)
                
                # Send only the NEW terminal line, not entire history
                self.task_response_queue.put({
                    'type': 'step_start',
                    'step': agent.step_count,
                    'command': parsed['command'],
                    'thinking': parsed.get('thinking', ''),
                    'command_history': list(state['commands']),
                    'terminal_line': term_msg  # Only send the new line
                })
                state['command_to_execute'] = parsed['command']
                state['state'] = 'execute_command'

            elif state['state'] == 'execute_command':
                self.playwright_command_queue.put(state['command_to_execute'])
                state['state'] = 'awaiting_command_result'

            elif state['state'] == 'process_command_result':
                result = state['result']
                status_line = ' SUCCESS\n' if result.success else ' FAILED\n'
                output_text = result.output if isinstance(result.output, str) else str(result.output)
                full_output = f"{status_line}{output_text}\n"
                state['terminal'].append(full_output)

                # Send only the NEW terminal line, not entire history
                self.task_response_queue.put({
                    'type': 'step_result',
                    'success': result.success,
                    'output': output_text,
                    'terminal_line': full_output  # Only send the new line
                })
                
                feedback = agent._build_feedback(result, state['task'])
                state['future'] = self.executor.submit(agent._call_llm, feedback)
                state['state'] = 'awaiting_llm_response'

        except Exception as e:
            self.task_response_queue.put({'type': 'task_error', 'error': str(e)})
            self.task_state = None


    def start_thread(self):
        """Start the Playwright worker thread"""
        if not self.thread_running:
            self.thread_running = True
            self.playwright_thread = threading.Thread(target=self._playwright_thread_worker, daemon=True)
            self.playwright_thread.start()
            print(" Playwright thread started")

    async def initialize_agent(self, config):
        """Initialize the browser agent"""
        print(" Initializing agent...")
        await self.broadcast({
            'type': 'terminal',
            'content': 'Initializing browser agent...\n',
            'style': 'info'
        })
        
        self.init_queue.put({'type': 'init', 'config': config})
        
        try:
            response = await asyncio.get_event_loop().run_in_executor(
                None, lambda: self.init_response_queue.get(timeout=30)
            )
            
            if response['type'] == 'init_success':
                await self.broadcast({
                    'type': 'terminal',
                    'content': f' Ready (Model: {response["model"]})\n',
                    'style': 'success'
                })
                await self.broadcast({'type': 'status', 'ready': True, 'message': 'Ready'})
                await self.start_streaming()
                print(" Agent initialized and streaming started")
            else:
                error_msg = response.get('error', 'Initialization failed')
                await self.broadcast({'type': 'error', 'message': error_msg})
                print(f" Init failed: {error_msg}")
        except Exception as e:
            error_msg = f"Initialization error: {str(e)}"
            await self.broadcast({'type': 'error', 'message': error_msg})
            print(f" {error_msg}")

    async def start_streaming(self):
        """Start video streaming"""
        if not self.streaming_active and self.agent_ready.is_set():
            self.screenshot_enabled.set()
            self.streaming_active = True
            self.screenshot_task = asyncio.create_task(self.stream_video())
            await self.broadcast({'type': 'stream_started', 'fps': self.fps})
            print(f" Video streaming started at {self.fps} FPS")

    async def stop_streaming(self):
        """Stop video streaming"""
        if self.streaming_active:
            self.screenshot_enabled.clear()
            self.streaming_active = False
            if self.screenshot_task:
                self.screenshot_task.cancel()
            await self.broadcast({'type': 'stream_stopped'})
            print("â¸ï¸ Video streaming stopped")

    async def stream_video(self):
        """Stream video frames to clients"""
        while self.streaming_active:
            try:
                shot = await asyncio.get_event_loop().run_in_executor(
                    None, lambda: self.screenshot_queue.get(timeout=1)
                )
                base64_data = base64.b64encode(shot).decode('utf-8')
                await self.broadcast({
                    'type': 'frame',
                    'data': f"data:image/png;base64,{base64_data}",
                    'timestamp': time.time()
                })
            except queue.Empty:
                await asyncio.sleep(0.01)
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f" Stream error: {e}")
                break
        print(" Video stream loop ended")

    async def execute_task(self, task):
        """Execute a task"""
        if not self.agent_ready.is_set():
            await self.broadcast({'type': 'error', 'message': 'Agent not initialized.'})
            return
            
        with self.task_lock:
            if self.task_state is not None:
                await self.broadcast({'type': 'error', 'message': 'A task is already running.'})
                return
        
        print(f" Executing task: {task}")
        await self.broadcast({
            'type': 'terminal',
            'content': f'\n{"="*70}\n TASK: {task}\n{"="*70}\n',
            'style': 'task'
        })
        
        self.task_queue.put({'type': 'execute_task', 'task': task})
        
        try:
            while True:
                try:
                    response = await asyncio.get_event_loop().run_in_executor(
                        None, lambda: self.task_response_queue.get(timeout=120)
                    )
                    rtype = response['type']
                    
                    if rtype == 'task_start':
                        await self.broadcast({'type': 'task_start', 'task': response['task']})
                        
                    elif rtype == 'step_start':
                        await self.broadcast({'type': 'command_history', 'commands': response['command_history']})
                        await self.broadcast({
                            'type': 'command',
                            'step': response['step'],
                            'command': response['command'],
                            'thinking': response['thinking']
                        })
                        # Only send the new terminal line
                        await self.broadcast({
                            'type': 'terminal',
                            'content': response['terminal_line'],  # Changed from 'terminal'
                            'style': 'output'
                        })
                        
                    elif rtype == 'step_result':
                        # Only send the new terminal line
                        await self.broadcast({
                            'type': 'terminal',
                            'content': response['terminal_line'],  # Changed from 'terminal'
                            'style': 'output'
                        })
                        
                    elif rtype == 'task_completed':
                        finish_msg = response.get('finish_message', response.get('reasoning', ''))
                        await self.broadcast({
                            'type': 'terminal',
                            'content': f'\n{"="*70}\n TASK COMPLETED\n{"="*70}\n\n{finish_msg}\n',
                            'style': 'success'
                        })
                        await self.broadcast({'type': 'command_history', 'commands': response['command_history']})
                        break
                        
                    elif rtype in ['task_error', 'parse_error']:
                        await self.broadcast({
                            'type': 'terminal',
                            'content': f' Error: {response["error"]}\n',
                            'style': 'error'
                        })
                        if rtype == 'task_error':
                            break
                            
                    elif rtype == 'max_steps_reached':
                        await self.broadcast({
                            'type': 'terminal',
                            'content': f'\nï¸ Maximum steps reached\n',
                            'style': 'warning'
                        })
                        break
                        
                    elif rtype == 'task_stopped':
                        await self.broadcast({
                            'type': 'terminal',
                            'content': f'\n Task stopped by user\n',
                            'style': 'warning'
                        })
                        break
                        
                except queue.Empty:
                    with self.task_lock:
                        if self.task_state is None:
                            break
        except Exception as e:
            print(f" Task execution error: {e}")
            await self.broadcast({
                'type': 'terminal',
                'content': f'\n Error: {str(e)}\n',
                'style': 'error'
            })
        finally:
            await self.broadcast({'type': 'task_end'})
            print(" Task execution complete")

    async def stop_task(self):
        """Stop the current task"""
        with self.task_lock:
            if self.task_state is not None:
                print("â¹ï¸ Stop button pressed - setting cancellation flag")
                self.task_cancelled.set()
                await self.broadcast({
                    'type': 'terminal',
                    'content': '\nâ¹ï¸ Stopping task...\n',
                    'style': 'warning'
                })
            else:
                print("ï¸ No task running to stop")

    async def send_message(self, ws, message):
        """Send message to a single websocket"""
        try:
            await ws.send_json(message)
        except ConnectionResetError:
            pass
        except Exception as e:
            print(f"Error sending message: {e}")

    async def broadcast(self, message):
        """Broadcast message to all connected clients"""
        if not self.websockets:
            return
        aws = [ws.send_json(message) for ws in self.websockets]
        await asyncio.gather(*aws, return_exceptions=True)

    async def on_shutdown(self, app):
        """Cleanup on server shutdown"""
        print("\n Shutting down server...")
        await self.stop_streaming()
        
        if self.thread_running:
            self.shutdown_event.set()
            self.task_cancelled.set()
            self.executor.shutdown(wait=False, cancel_futures=True)
            self.thread_running = False
            
            if self.playwright_thread and self.playwright_thread.is_alive():
                self.playwright_thread.join(timeout=3)
        
        print(" Shutdown complete.")

    def run(self):
        """Start the server"""
        self.start_thread()
        self.app.on_shutdown.append(self.on_shutdown)
        
        # Use environment PORT if available (for Render/production)
        actual_port = int(os.environ.get('PORT', self.port))
        actual_host = os.environ.get('HOST', '0.0.0.0')
        
        print(f" Server running at http://{actual_host}:{actual_port}")
        print(f" Landing page: http://{actual_host}:{actual_port}/")
        print(f"ï¸  Application: http://{actual_host}:{actual_port}/app")
        print(f" Static files: {Path(__file__).parent / 'static'}")
        print(f" Make sure GROQ_API_KEY is set in environment")
        
        web.run_app(self.app, host=actual_host, port=actual_port, print=lambda x: None)


def main():
    parser = argparse.ArgumentParser(description="Run the continuous streaming browser server.")
    parser.add_argument('--host', default=os.environ.get('HOST', '0.0.0.0'), help='Host to bind to')
    parser.add_argument('--port', type=int, default=int(os.environ.get('PORT', 8085)), help='Port to bind to')
    parser.add_argument('--fps', type=int, default=60, help='Frames per second for streaming')
    args = parser.parse_args()
    
    # Check for API key
    if not os.getenv('GROQ_API_KEY'):
        print("ï¸  Warning: GROQ_API_KEY not found in environment")
        print("   Set it with: export GROQ_API_KEY='your-key-here'")
    
    server = CombinedVideoServer(host=args.host, port=args.port, fps=args.fps)
    
    try:
        server.run()
    except KeyboardInterrupt:
        print("\n Server stopped by user.")


if __name__ == '__main__':
    main()