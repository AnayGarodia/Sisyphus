#!/usr/bin/env python3

"""
Combined UltraSmooth Browser Video Server:
 - 60 FPS streaming screenshots
 - Full command history and terminal tracking
 - Continuous streaming with greenlet-safe command execution (Fix v3)
"""

import asyncio
import json
import os
import sys
import base64
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
    sys.exit(1)


class CombinedVideoServer:
    """Continuous 60fps video + complete command/terminal tracking."""

    def __init__(self, host="localhost", port=8085, fps=60):
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

        self.task_state = None
        self.task_lock = threading.Lock()
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
        self.app.router.add_get('/app.html', self.serve_app)
        
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
        print(f"✅ Client connected. Total: {len(self.websockets)}")

        await self.send_message(ws, {
            'type': 'status',
            'message': 'Connected',
            'ready': self.agent_ready.is_set()
        })

        try:
            async for msg in ws:
                if msg.type == web.WSMsgType.TEXT:
                    await self.handle_message(ws, msg.data)
        finally:
            self.websockets.discard(ws)
            print(f"❌ Disconnected. Total: {len(self.websockets)}")
        return ws

    async def handle_message(self, ws, data):
        try:
            message = json.loads(data)
            msg_type = message.get('type')
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
            await self.send_message(ws, {'type': 'error', 'message': str(e)})

    def _playwright_thread_worker(self):
        agent = None
        last_screenshot_time = 0
        try:
            command = self.init_queue.get(timeout=60)
            if command.get('type') == 'init':
                config = command.get('config', {})
                api_key = config.get('api_key') or os.getenv('GROQ_API_KEY')
                if not api_key:
                    raise ValueError("GROQ_API_KEY not found")
                model = config.get('model', 'llama-3.1-8b-instant')
                agent = LLMBrowserAgent(api_key=api_key, headless=False, model=model)
                self.agent = agent
                self.agent_ready.set()
                self.init_response_queue.put({'type': 'init_success', 'model': agent.model})
            else:
                self.init_response_queue.put({'type': 'init_error', 'error': 'Init timeout'})
                return

            while self.thread_running and not self.shutdown_event.is_set():
                now = time.time()
                if self.screenshot_enabled.is_set() and agent and agent.browser:
                    if now - last_screenshot_time >= self.frame_interval:
                        try:
                            byteshot = agent.browser.page.screenshot(type='png')
                            if self.screenshot_queue.qsize() < 15:
                                self.screenshot_queue.put_nowait(byteshot)
                            last_screenshot_time = now
                        except Exception:
                            pass

                with self.task_lock:
                    if self.task_state:
                        self._step_task_state(agent)

                try:
                    cmd_to_run = self.playwright_command_queue.get_nowait()
                    result = agent._execute_command(cmd_to_run)
                    with self.task_lock:
                        if self.task_state and self.task_state['state'] == 'awaiting_command_result':
                            self.task_state['result'] = result
                            self.task_state['state'] = 'process_command_result'
                except queue.Empty:
                    pass

                try:
                    command = self.task_queue.get(timeout=0.001)
                    if command.get('type') == 'execute_task':
                        self._init_task_state(agent, command.get('task', ''))
                    elif command.get('type') == 'stop_task':
                        with self.task_lock:
                            self.task_state = None
                        self.task_response_queue.put({'type': 'task_stopped'})
                except queue.Empty:
                    pass

                time.sleep(0.001)
        finally:
            if agent:
                try: agent.close() 
                except: pass
            print("📚 Playwright thread ended.")

    def _init_task_state(self, agent, task):
        agent.step_count = 0
        agent.conversation_history = []
        self.task_state = {
            'task': task, 'state': 'prompt_llm', 'future': None,
            'max_steps': agent.DEFAULT_MAX_STEPS, 'commands': [], 'terminal': []
        }
        self.task_response_queue.put({'type': 'task_start', 'task': task})

    def _step_task_state(self, agent):
        state = self.task_state
        if not state: return

        try:
            if state['state'] == 'awaiting_llm_response':
                future = state.get('future')
                if not future or not future.done(): return
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
                        'type': 'task_completed', 'reasoning': parsed.get('reasoning', ''),
                        'terminal': state['terminal'], 'command_history': state['commands'],
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
                cmd_entry = {'step': agent.step_count, 'command': parsed['command'], 'reasoning': parsed.get('reasoning', '')}
                state['commands'].append(cmd_entry)
                term_msg = f"\n--- Step {agent.step_count} ---\nReasoning: {parsed.get('reasoning', '')}\nCommand: {parsed['command']}\n"
                state['terminal'].append(term_msg)
                
                self.task_response_queue.put({
                    'type': 'step_start', 'step': agent.step_count,
                    'command': parsed['command'], 'reasoning': parsed.get('reasoning', ''),
                    'command_history': list(state['commands']), 'terminal': ''.join(state['terminal'])
                })
                state['command_to_execute'] = parsed['command']
                state['state'] = 'execute_command'

            elif state['state'] == 'execute_command':
                self.playwright_command_queue.put(state['command_to_execute'])
                state['state'] = 'awaiting_command_result'

            elif state['state'] == 'process_command_result':
                result = state['result']
                status_line = '✔ SUCCESS\n' if result.success else '✗ FAILED\n'
                output_text = result.output if isinstance(result.output, str) else str(result.output)
                full_output = f"{status_line}{output_text}\n"
                state['terminal'].append(full_output)

                self.task_response_queue.put({
                    'type': 'step_result', 'success': result.success,
                    'output': output_text, 'terminal': ''.join(state['terminal'])
                })
                
                feedback = agent._build_feedback(result, state['task'])
                state['future'] = self.executor.submit(agent._call_llm, feedback)
                state['state'] = 'awaiting_llm_response'

        except Exception as e:
            self.task_response_queue.put({'type': 'task_error', 'error': str(e)})
            self.task_state = None

    def start_thread(self):
        if not self.thread_running:
            self.thread_running = True
            self.playwright_thread = threading.Thread(target=self._playwright_thread_worker, daemon=True)
            self.playwright_thread.start()

    async def initialize_agent(self, config):
        await self.broadcast({'type': 'terminal', 'content': 'Initializing browser agent...\n', 'style': 'info'})
        self.init_queue.put({'type': 'init', 'config': config})
        try:
            response = await asyncio.get_event_loop().run_in_executor(None, lambda: self.init_response_queue.get(timeout=30))
            if response['type'] == 'init_success':
                await self.broadcast({'type': 'terminal', 'content': f'✔ Ready (Model: {response["model"]})\n', 'style': 'success'})
                await self.broadcast({'type': 'status', 'ready': True})
                await self.start_streaming()
            else:
                await self.broadcast({'type': 'error', 'message': response.get('error', 'Initialization failed')})
        except Exception as e:
            await self.broadcast({'type': 'error', 'message': str(e)})

    async def start_streaming(self):
        if not self.streaming_active and self.agent_ready.is_set():
            self.screenshot_enabled.set()
            self.streaming_active = True
            self.screenshot_task = asyncio.create_task(self.stream_video())
            await self.broadcast({'type': 'stream_started', 'fps': self.fps})
            print(f"✅ Video streaming at {self.fps} FPS")

    async def stop_streaming(self):
        if self.streaming_active:
            self.screenshot_enabled.clear()
            self.streaming_active = False
            if self.screenshot_task: self.screenshot_task.cancel()
            await self.broadcast({'type': 'stream_stopped'})

    async def stream_video(self):
        while self.streaming_active:
            try:
                shot = await asyncio.get_event_loop().run_in_executor(None, lambda: self.screenshot_queue.get(timeout=1))
                base64_data = base64.b64encode(shot).decode('utf-8')
                await self.broadcast({'type': 'frame', 'data': f"data:image/png;base64,{base64_data}", 'timestamp': time.time()})
            except queue.Empty:
                await asyncio.sleep(0.01)
            except asyncio.CancelledError: break
            except Exception as e:
                print(f"❌ Stream error: {e}")
                break
        print("🛑 Video stream loop ended")

    async def execute_task(self, task):
        if not self.agent_ready.is_set():
            await self.broadcast({'type': 'error', 'message': 'Agent not initialized.'})
            return
        with self.task_lock:
            if self.task_state is not None:
                await self.broadcast({'type': 'error', 'message': 'A task is already running.'})
                return
                
        await self.broadcast({
            'type': 'terminal',
            'content': f'\n{"="*70}\nTASK: {task}\n{"="*70}\n',
            'style': 'task'
        })
        
        self.task_queue.put({'type': 'execute_task', 'task': task})
        
        try:
            while True:
                try:
                    response = await asyncio.get_event_loop().run_in_executor(
                        None, lambda: self.task_response_queue.get(timeout=120))
                    rtype = response['type']
                    
                    if rtype == 'task_start':
                        await self.broadcast({'type': 'task_start', 'task': response['task']})
                        
                    elif rtype == 'step_start':
                        await self.broadcast({'type': 'command_history', 'commands': response['command_history']})
                        await self.broadcast({
                            'type': 'command',
                            'step': response['step'],
                            'command': response['command'],
                            'reasoning': response['reasoning']
                        })
                        await self.broadcast({'type': 'terminal', 'content': response['terminal'], 'style': 'output'})
                        
                    elif rtype == 'step_result':
                        await self.broadcast({'type': 'terminal', 'content': response['terminal'], 'style': 'output'})
                        
                    elif rtype == 'task_completed':
                        await self.broadcast({
                            'type': 'terminal',
                            'content': f'\n{"="*70}\n✔ DONE\n{"="*70}\n\n{response["reasoning"]}\n',
                            'style': 'success'
                        })
                        await self.broadcast({'type': 'command_history', 'commands': response['command_history']})
                        break
                        
                    elif rtype in ['task_error', 'parse_error']:
                        await self.broadcast({'type': 'terminal', 'content': f'Error: {response["error"]}\n', 'style': 'error'})
                        if rtype == 'task_error': break
                            
                    elif rtype == 'max_steps_reached':
                        await self.broadcast({'type': 'terminal', 'content': f'\n⚠ Max steps reached\n', 'style': 'warning'})
                        break
                        
                    elif rtype == 'task_stopped':
                        break
                        
                except queue.Empty:
                    with self.task_lock:
                        if self.task_state is None: break
        except Exception as e:
            await self.broadcast({'type': 'terminal', 'content': f'\n✗ {str(e)}\n', 'style': 'error'})
        finally:
            await self.broadcast({'type': 'task_end'})

    async def stop_task(self):
        with self.task_lock:
            if self.task_state is not None:
                self.task_queue.put({'type': 'stop_task'})
                await self.broadcast({'type': 'terminal', 'content': '\n[Stopping task...]\n', 'style': 'warning'})

    async def send_message(self, ws, message):
        try: await ws.send_json(message)
        except ConnectionResetError: pass

    async def broadcast(self, message):
        if not self.websockets: return
        aws = [ws.send_json(message) for ws in self.websockets]
        await asyncio.gather(*aws, return_exceptions=True)

    async def on_shutdown(self, app):
        print("\nShutting down server...")
        await self.stop_streaming()
        if self.thread_running:
            self.shutdown_event.set()
            self.executor.shutdown(wait=False, cancel_futures=True)
            self.thread_running = False
            if self.playwright_thread and self.playwright_thread.is_alive():
                self.playwright_thread.join(timeout=3)
        print("Shutdown complete.")

    def run(self):
        self.start_thread()
        self.app.on_shutdown.append(self.on_shutdown)
        print(f"🚀 Server running at http://{self.host}:{self.port}")
        print(f"📄 Landing page: http://{self.host}:{self.port}/")
        print(f"🖥️  Application: http://{self.host}:{self.port}/app.html")
        web.run_app(self.app, host=self.host, port=self.port, print=lambda x: None)


def main():
    parser = argparse.ArgumentParser(description="Run the continuous streaming browser server.")
    parser.add_argument('--host', default='localhost')
    parser.add_argument('--port', type=int, default=8085)
    parser.add_argument('--fps', type=int, default=60)
    args = parser.parse_args()
    server = CombinedVideoServer(host=args.host, port=args.port, fps=args.fps)
    try:
        server.run()
    except KeyboardInterrupt:
        print("\n🛑 Server stopped by user.")


if __name__ == '__main__':
    import argparse
    main()