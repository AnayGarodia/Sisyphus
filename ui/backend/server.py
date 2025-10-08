#!/usr/bin/env python3

"""
Combined UltraSmooth Browser Video Server:
 - 60 FPS streaming screenshots (from version 1)
 - Full command history and terminal tracking (from version 2)
 - Never blocks video during agent task execution (Continuous Streaming Fix)
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
import concurrent.futures # Added for non-blocking task execution

try:
    from aiohttp import web
    import aiohttp_cors
except ImportError:
    print("Error: aiohttp required. Install with: pip install aiohttp aiohttp-cors")
    sys.exit(1)

# Import agent
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
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
        
        # KEY CHANGE: Thread pool to run blocking tasks without freezing the video stream
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=2)

        self.agent = None
        self.agent_ready = threading.Event()
        self.init_queue = queue.Queue()
        self.init_response_queue = queue.Queue()
        self.task_queue = queue.Queue()
        self.task_response_queue = queue.Queue()

        # Task state & buffers
        self.task_state = None
        self.task_lock = threading.Lock()
        self.streaming_active = False
        self.screenshot_task = None

        self._setup_routes()
        self._setup_cors()

    def _setup_routes(self):
        self.app.router.add_get('/ws', self.websocket_handler)
        self.app.router.add_get('/', self.index_handler)
        self.app.router.add_static('/static', Path(__file__).parent.parent / 'frontend', name='static')

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

    async def index_handler(self, request):
        html_path = Path(__file__).parent.parent / 'frontend' / 'index.html'
        return web.FileResponse(html_path)

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
        """Continuous loop: high-FPS screenshots + nonblocking task management."""
        agent = None
        last_screenshot_time = 0
        frame_count = 0

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
                    try:
                        page = agent.browser.page
                        if page and now - last_screenshot_time >= self.frame_interval:
                            byteshot = page.screenshot(type='png')
                            if self.screenshot_queue.qsize() < 15:
                                self.screenshot_queue.put_nowait(byteshot)
                            frame_count += 1
                            last_screenshot_time = now
                    except Exception as e:
                        if frame_count % 100 == 0:
                            print(f"Screenshot error: {e}")

                with self.task_lock:
                    if self.task_state:
                        # KEY CHANGE: This function now runs instantly and schedules blocking calls
                        # in the background, so it doesn't interrupt screenshotting.
                        self._step_task_state_non_blocking(agent)

                try:
                    command = self.task_queue.get(timeout=0.001)
                    ttype = command.get('type')
                    if ttype == 'execute_task':
                        if agent:
                            self._init_task_state(agent, command.get('task', ''))
                        else:
                            self.task_response_queue.put({'type': 'task_error', 'error': 'Agent not initialized'})
                    elif ttype == 'stop_task':
                        with self.task_lock:
                            self.task_state = None
                        self.task_response_queue.put({'type': 'task_stopped'})
                    elif ttype == 'shutdown':
                        break
                except queue.Empty:
                    pass

                time.sleep(0.001) # Very short sleep to prevent high CPU usage
        except Exception as e:
            self.init_response_queue.put({'type': 'init_error', 'error': str(e)})
        finally:
            if agent:
                try:
                    agent.close()
                except:
                    pass
            print(f"🔚 Thread ended. Frames: {frame_count}")

    def _init_task_state(self, agent, task):
        agent.step_count = 0
        agent.conversation_history = []
        agent.api_calls_made = 0
        agent.consecutive_failures = 0
        
        self.task_state = {
            'task': task,
            'state': 'prompt_llm',
            'future': None, # To hold the future object for async operations
            'max_steps': agent.DEFAULT_MAX_STEPS,
            'commands': [],
            'terminal': []
        }
        self.task_response_queue.put({'type': 'task_start', 'task': task})

    # KEY CHANGE: This is the new, non-blocking state machine.
    def _step_task_state_non_blocking(self, agent):
        """
        Processes task steps by submitting blocking calls to a thread pool,
        keeping the main worker thread free for continuous screenshotting.
        """
        state = self.task_state
        if not state:
            return

        try:
            # === ASYNC AWAIT STAGE ===
            # If we are waiting for a future to complete, check on it.
            if state['state'].startswith('await_'):
                future = state.get('future')
                if not future or not future.done():
                    return # Not ready, return immediately to allow screenshotting

                try:
                    result = future.result()
                    state['future'] = None
                except Exception as e:
                    self.task_response_queue.put({'type': 'task_error', 'error': f"Async task failed: {e}"})
                    self.task_state = None
                    return

                # Transition to the next state based on what we were waiting for
                if state['state'] == 'await_llm_response':
                    state['llm_response'] = result
                    state['state'] = 'parse_response'
                elif state['state'] == 'await_command':
                    state['result'] = result
                    state['state'] = 'process_command_result'
            
            # === STATE MACHINE LOGIC ===
            # The machine moves from state to state. Fast states execute immediately.
            # Slow (blocking) states submit a task to the executor and move to an 'await_' state.

            if state['state'] == 'prompt_llm':
                prompt = (f"Task: {state['task']}\n\nWhat is the FIRST single command needed?")
                state['future'] = self.executor.submit(agent._call_llm, prompt)
                state['state'] = 'await_llm_response'
            
            elif state['state'] == 'parse_response':
                parsed = agent._parse_response(state['llm_response'])
                if 'error' in parsed:
                    self.task_response_queue.put({'type': 'parse_error', 'error': parsed['error']})
                    retry_prompt = f"Invalid format: {parsed['error']}. Reformat using COMMAND and REASONING or DONE."
                    state['future'] = self.executor.submit(agent._call_llm, retry_prompt)
                    state['state'] = 'await_llm_response' # Submit retry and wait again
                    return

                if parsed.get('done'):
                    title, url = agent._get_page_context()
                    self.task_response_queue.put({
                        'type': 'task_completed', 'reasoning': parsed.get('reasoning', ''),
                        'steps': agent.step_count, 'api_calls': agent.api_calls_made,
                        'title': title, 'url': url, 'command_history': state['commands'],
                        'terminal': state['terminal']
                    })
                    self.task_state = None
                    return
                
                agent.step_count += 1
                if agent.step_count > state['max_steps']:
                    self.task_response_queue.put({'type': 'max_steps_reached', 'max_steps': state['max_steps']})
                    self.task_state = None
                    return
                
                state['parsed'] = parsed
                state['state'] = 'announce_step'

            elif state['state'] == 'announce_step':
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
                command = state['command_to_execute']
                state['future'] = self.executor.submit(agent._execute_command, command)
                state['state'] = 'await_command'

            elif state['state'] == 'process_command_result':
                result = state['result']
                status_line = '✓ SUCCESS\n' if result.success else '✗ FAILED\n'
                output_text = result.output if isinstance(result.output, str) else str(result.output)
                full_output = f"{status_line}{output_text}\n"
                state['terminal'].append(full_output)

                self.task_response_queue.put({
                    'type': 'step_result', 'success': result.success,
                    'output': output_text, 'terminal': ''.join(state['terminal'])
                })
                
                agent.consecutive_failures = 0 if result.success else agent.consecutive_failures + 1
                state['state'] = 'get_next_action'

            elif state['state'] == 'get_next_action':
                feedback = agent._build_feedback(state['result'], state['task'])
                state['future'] = self.executor.submit(agent._call_llm, feedback)
                state['state'] = 'await_llm_response'

        except Exception as e:
            self.task_response_queue.put({'type': 'task_error', 'error': str(e)})
            self.task_state = None

    def start_thread(self):
        if not self.thread_running:
            self.thread_running = True
            self.playwright_thread = threading.Thread(target=self._playwright_thread_worker, daemon=True)
            self.playwright_thread.start()
            time.sleep(0.5)

    async def initialize_agent(self, config):
        await self.broadcast({'type': 'terminal', 'content': 'Initializing browser agent...\n', 'style': 'info'})
        self.init_queue.put({'type': 'init', 'config': config})
        try:
            response = await asyncio.get_event_loop().run_in_executor(
                None, lambda: self.init_response_queue.get(timeout=30))
            if response['type'] == 'init_success':
                await self.broadcast({'type': 'terminal', 'content': f'✓ Ready (Model: {response["model"]})\n', 'style': 'success'})
                await self.broadcast({'type': 'status', 'ready': True})
                await self.start_streaming()
            elif response['type'] == 'init_error':
                await self.broadcast({'type': 'error', 'message': response['error']})
        except Exception as e:
            await self.broadcast({'type': 'error', 'message': str(e)})

    async def start_streaming(self):
        if not self.streaming_active and self.agent_ready.is_set():
            print("🎥 Starting video stream...")
            self.screenshot_enabled.set()
            self.streaming_active = True
            self.screenshot_task = asyncio.create_task(self.stream_video())
            await self.broadcast({'type': 'stream_started', 'fps': self.fps})
            print(f"✅ Video streaming at {self.fps} FPS")

    async def stop_streaming(self):
        if self.streaming_active:
            self.screenshot_enabled.clear()
            self.streaming_active = False
            if self.screenshot_task:
                self.screenshot_task.cancel()
            await self.broadcast({'type': 'stream_stopped'})

    async def stream_video(self):
        print("🎥 Video stream loop started")
        while self.streaming_active:
            try:
                shot = await asyncio.get_event_loop().run_in_executor(
                    None, lambda: self.screenshot_queue.get(timeout=1))
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
                
        await self.broadcast({'type': 'terminal', 'content': f'\n{"="*70}\nTASK: {task}\n{"="*70}\n', 'style': 'task'})
        self.task_queue.put({'type': 'execute_task', 'task': task})
        
        # This loop now just forwards messages from the agent thread to the websocket clients.
        while True:
            try:
                response = await asyncio.get_event_loop().run_in_executor(
                    None, lambda: self.task_response_queue.get(timeout=120))
                
                rtype = response['type']
                await self.broadcast(response) # Broadcast the whole message

                if rtype in ['task_completed', 'task_error', 'max_steps_reached', 'task_stopped']:
                    break
            except queue.Empty:
                with self.task_lock:
                    if self.task_state is None:
                        break # Task finished between checks
        
        await self.broadcast({'type': 'task_end'})

    async def stop_task(self):
        with self.task_lock:
            if self.task_state is not None:
                self.task_queue.put({'type': 'stop_task'})
                await self.broadcast({'type': 'terminal', 'content': '\n[Stopping task...]\n', 'style': 'warning'})

    async def send_message(self, ws, message):
        try:
            await ws.send_json(message)
        except ConnectionResetError:
            print("Could not send to a closed websocket.")

    async def broadcast(self, message):
        if not self.websockets:
            return
        aws = [ws.send_json(message) for ws in self.websockets]
        await asyncio.gather(*aws, return_exceptions=True)

    async def on_shutdown(self, app):
        print("\nShutting down server...")
        await self.stop_streaming()
        if self.thread_running:
            self.shutdown_event.set()
            # KEY CHANGE: Cleanly shut down the thread pool
            self.executor.shutdown(wait=False, cancel_futures=True)
            self.thread_running = False
            self.task_queue.put({'type': 'shutdown'})
            if self.playwright_thread:
                self.playwright_thread.join(timeout=5)
        print("Shutdown complete.")

    def run(self):
        self.start_thread()
        self.app.on_shutdown.append(self.on_shutdown)
        print(f"""
╔═════════════════════════════════════════════════════════╗
║   🎥 CONTINUOUS STREAMING BROWSER SERVER               ║
╚═════════════════════════════════════════════════════════╝
🌐 http://{self.host}:{self.port}
📡 ws://{self.host}:{self.port}/ws
🎥 {self.fps} FPS streaming with non-blocking agent actions
""")
        web.run_app(self.app, host=self.host, port=self.port, print=lambda x: None)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Run the continuous streaming browser server.")
    parser.add_argument('--host', default='localhost', help='Host to run the server on.')
    parser.add_argument('--port', type=int, default=8085, help='Port to run the server on.')
    parser.add_argument('--fps', type=int, default=60, help='Frames per second for video streaming.')
    args = parser.parse_args()
    server = CombinedVideoServer(host=args.host, port=args.port, fps=args.fps)
    try:
        server.run()
    except KeyboardInterrupt:
        print("\n🛑 Bye!")


if __name__ == '__main__':
    main()