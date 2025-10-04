#!/usr/bin/env python3
"""
Unified WebSocket server that uses agent.py for reasoning and execution
Pure async Playwright for screenshot streaming only
"""

import asyncio
import json
import os
import sys
import base64
from pathlib import Path
from typing import Set, Dict, Any, Optional
import time
import threading

try:
    from aiohttp import web
    import aiohttp_cors
except ImportError:
    print("Error: aiohttp required. Install with: pip install aiohttp aiohttp-cors")
    sys.exit(1)

try:
    from playwright.async_api import async_playwright, Browser, Page, BrowserContext
except ImportError:
    print("Error: playwright required. Install with: pip install playwright")
    print("Then run: playwright install chromium")
    sys.exit(1)

# Import your agent.py
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

try:
    from agent import LLMBrowserAgent
except ImportError as e:
    print(f"Error importing agent: {e}")
    sys.exit(1)


class ScreenshotStreamer:
    """Separate async browser instance ONLY for screenshots."""
    
    def __init__(self):
        self.playwright = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.sync_page = None  # Reference to agent's sync page
    
    async def start(self):
        """Start async browser for screenshots."""
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(headless=False)
        self.context = await self.browser.new_context(
            viewport={'width': 1280, 'height': 720}
        )
        self.page = await self.context.new_page()
        await self.page.goto('about:blank')
    
    def connect_to_sync_page(self, sync_page):
        """Connect to the sync playwright page from agent.py."""
        self.sync_page = sync_page
    
    async def screenshot(self) -> Optional[bytes]:
        """Capture screenshot from the connected page."""
        if not self.page:
            return None
        try:
            return await self.page.screenshot(type='png')
        except Exception:
            return None
    
    async def sync_url(self):
        """Sync our page URL with the agent's page."""
        if self.sync_page and self.page:
            try:
                target_url = self.sync_page.url
                current_url = self.page.url
                if target_url != current_url:
                    await self.page.goto(target_url, wait_until='domcontentloaded', timeout=5000)
            except Exception:
                pass
    
    async def close(self):
        """Close browser."""
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()


class AgentUIServer:
    """WebSocket server with agent.py integration and live streaming."""
    
    def __init__(self, host: str = "localhost", port: int = 8080):
        self.host = host
        self.port = port
        self.app = web.Application()
        self.websockets: Set[web.WebSocketResponse] = set()
        
        self.agent: Optional[LLMBrowserAgent] = None
        self.streamer: Optional[ScreenshotStreamer] = None
        self.task_running = False
        self.streaming_active = False
        
        # Streaming configuration
        self.fps = 20
        self.frame_interval = 1.0 / self.fps
        self.last_frame_time = 0
        self.screenshot_task = None
        self.sync_task = None
        
        # Lock for agent operations
        self.agent_lock = threading.Lock()
        
        self._setup_routes()
        self._setup_cors()
    
    def _setup_routes(self):
        """Configure HTTP and WebSocket routes."""
        self.app.router.add_get('/ws', self.websocket_handler)
        self.app.router.add_get('/', self.index_handler)
        self.app.router.add_static('/static', 
                                   Path(__file__).parent.parent / 'frontend',
                                   name='static')
    
    def _setup_cors(self):
        """Setup CORS for development."""
        cors = aiohttp_cors.setup(self.app, defaults={
            "*": aiohttp_cors.ResourceOptions(
                allow_credentials=True,
                expose_headers="*",
                allow_headers="*"
            )
        })
        
        for route in list(self.app.router.routes()):
            cors.add(route)
    
    async def index_handler(self, request):
        """Serve main HTML page."""
        html_path = Path(__file__).parent.parent / 'frontend' / 'index.html'
        return web.FileResponse(html_path)
    
    async def websocket_handler(self, request):
        """Handle WebSocket connections."""
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        
        self.websockets.add(ws)
        print(f"Client connected. Total clients: {len(self.websockets)}")
        
        await self.send_message(ws, {
            'type': 'status',
            'message': 'Connected to AI Browser Agent',
            'ready': False
        })
        
        try:
            async for msg in ws:
                if msg.type == web.WSMsgType.TEXT:
                    await self.handle_message(ws, msg.data)
                elif msg.type == web.WSMsgType.ERROR:
                    print(f'WebSocket error: {ws.exception()}')
        finally:
            self.websockets.discard(ws)
            print(f"Client disconnected. Total clients: {len(self.websockets)}")
        
        return ws
    
    async def handle_message(self, ws: web.WebSocketResponse, data: str):
        """Process incoming WebSocket messages."""
        try:
            message = json.loads(data)
            msg_type = message.get('type')
            
            if msg_type == 'execute_task':
                await self.execute_task(message.get('task', ''))
            
            elif msg_type == 'stop_task':
                self.task_running = False
                await self.broadcast({
                    'type': 'terminal',
                    'content': '\n[Task stopped by user]\n',
                    'style': 'warning'
                })
            
            elif msg_type == 'initialize':
                await self.initialize_agent(message.get('config', {}))
        
        except json.JSONDecodeError:
            await self.send_message(ws, {
                'type': 'error',
                'message': 'Invalid JSON message'
            })
        except Exception as e:
            await self.send_message(ws, {
                'type': 'error',
                'message': f'Error: {str(e)}'
            })
    
    async def initialize_agent(self, config: Dict[str, Any]):
        """Initialize the agent from agent.py."""
        try:
            await self.broadcast({
                'type': 'terminal',
                'content': 'Initializing browser agent...\n',
                'style': 'info'
            })
            
            # Initialize your agent.py in a thread
            loop = asyncio.get_event_loop()
            
            def create_agent():
                api_key = config.get('api_key') or os.getenv('GROQ_API_KEY')
                if not api_key:
                    raise ValueError("GROQ_API_KEY not found")
                
                model = config.get('model', 'llama-3.3-70b-versatile')
                agent = LLMBrowserAgent(
                    api_key=api_key,
                    headless=False,
                    model=model
                )
                return agent
            
            self.agent = await loop.run_in_executor(None, create_agent)
            
            # Initialize screenshot streamer
            self.streamer = ScreenshotStreamer()
            await self.streamer.start()
            
            # Connect streamer to agent's page
            self.streamer.connect_to_sync_page(self.agent.browser.page)
            
            await self.broadcast({
                'type': 'terminal',
                'content': f'✓ Agent initialized (Model: {self.agent.model})\n',
                'style': 'success'
            })
            
            await self.broadcast({
                'type': 'status',
                'ready': True,
                'message': 'Agent ready'
            })
            
            # Start streaming
            await self.start_streaming()
            
        except Exception as e:
            await self.broadcast({
                'type': 'terminal',
                'content': f'✗ Initialization failed: {str(e)}\n',
                'style': 'error'
            })
    
    async def start_streaming(self):
        """Start screenshot streaming loop."""
        if self.streaming_active or not self.streamer:
            return
        
        self.streaming_active = True
        self.screenshot_task = asyncio.create_task(self.screenshot_loop())
        self.sync_task = asyncio.create_task(self.sync_loop())
        
        await self.broadcast({
            'type': 'stream_started',
            'fps': self.fps
        })
        
        print(f"Screenshot streaming started at {self.fps} FPS")
    
    async def stop_streaming(self):
        """Stop screenshot streaming loop."""
        self.streaming_active = False
        
        if self.screenshot_task:
            self.screenshot_task.cancel()
            try:
                await self.screenshot_task
            except asyncio.CancelledError:
                pass
            self.screenshot_task = None
        
        if self.sync_task:
            self.sync_task.cancel()
            try:
                await self.sync_task
            except asyncio.CancelledError:
                pass
            self.sync_task = None
        
        await self.broadcast({
            'type': 'stream_stopped'
        })
        
        print("Screenshot streaming stopped")
    
    async def sync_loop(self):
        """Periodically sync streamer page with agent page."""
        while self.streaming_active:
            try:
                await asyncio.sleep(0.1)
                if self.streamer:
                    await self.streamer.sync_url()
            except asyncio.CancelledError:
                break
            except Exception:
                pass
    
    async def screenshot_loop(self):
        """Continuous screenshot capture and broadcast loop."""
        while self.streaming_active:
            try:
                current_time = time.time()
                
                # Rate limiting
                time_since_last = current_time - self.last_frame_time
                if time_since_last < self.frame_interval:
                    await asyncio.sleep(self.frame_interval - time_since_last)
                    continue
                
                self.last_frame_time = current_time
                
                # Capture screenshot
                screenshot_bytes = await self.streamer.screenshot()
                
                if screenshot_bytes:
                    # Convert to base64 data URL
                    base64_data = base64.b64encode(screenshot_bytes).decode('utf-8')
                    data_url = f"data:image/png;base64,{base64_data}"
                    
                    # Broadcast to all connected clients
                    await self.broadcast({
                        'type': 'frame',
                        'data': data_url,
                        'timestamp': current_time
                    })
                
            except asyncio.CancelledError:
                break
            except Exception:
                await asyncio.sleep(0.05)
    
    async def execute_task(self, task: str):
        """Execute task using agent.py."""
        if not self.agent:
            await self.broadcast({
                'type': 'error',
                'message': 'Agent not initialized'
            })
            return
        
        if self.task_running:
            await self.broadcast({
                'type': 'error',
                'message': 'A task is already running'
            })
            return
        
        self.task_running = True
        
        await self.broadcast({
            'type': 'task_start',
            'task': task
        })
        
        await self.broadcast({
            'type': 'terminal',
            'content': f'\n{"="*70}\nTASK: {task}\n{"="*70}\n',
            'style': 'task'
        })
        
        try:
            # Run agent.execute_task in executor to avoid blocking
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                self._execute_task_with_agent,
                task
            )
        except Exception as e:
            await self.broadcast({
                'type': 'terminal',
                'content': f'\n✗ Error: {str(e)}\n',
                'style': 'error'
            })
        finally:
            self.task_running = False
            await self.broadcast({
                'type': 'task_end'
            })
    
    def _execute_task_with_agent(self, task: str):
        """Execute task using agent.py (runs in executor thread)."""
        agent = self.agent
        max_steps = agent.DEFAULT_MAX_STEPS
        
        # Reset agent state
        agent.step_count = 0
        agent.conversation_history = []
        agent.api_calls_made = 0
        agent.consecutive_failures = 0
        
        # Get initial LLM response
        try:
            initial_prompt = (
                f"Task: {task}\n\n"
                f"What is the FIRST single command needed to accomplish this task?\n"
                f"Respond with ONE command only."
            )
            llm_response = agent._call_llm(initial_prompt)
        except Exception as e:
            asyncio.run_coroutine_threadsafe(
                self.broadcast({
                    'type': 'terminal',
                    'content': f'LLM Error: {e}\n',
                    'style': 'error'
                }),
                asyncio.get_event_loop()
            )
            return
        
        # Multi-step execution loop from agent.py
        while agent.step_count < max_steps and self.task_running:
            agent.step_count += 1
            
            # Parse response
            parsed = agent._parse_response(llm_response)
            
            if 'error' in parsed:
                asyncio.run_coroutine_threadsafe(
                    self.broadcast({
                        'type': 'terminal',
                        'content': f'Parse Error: {parsed["error"]}\n',
                        'style': 'error'
                    }),
                    asyncio.get_event_loop()
                )
                
                try:
                    llm_response = agent._call_llm(
                        f"Your response was invalid: {parsed['error']}\n\n"
                        "Please respond with either:\n"
                        "  COMMAND: <single command>\n"
                        "  REASONING: <why>\n\n"
                        "OR:\n"
                        "  DONE\n"
                        "  REASONING: <what you accomplished>"
                    )
                except Exception as e:
                    asyncio.run_coroutine_threadsafe(
                        self.broadcast({
                            'type': 'terminal',
                            'content': f'LLM Error: {e}\n',
                            'style': 'error'
                        }),
                        asyncio.get_event_loop()
                    )
                    break
                continue
            
            if parsed.get('done'):
                reasoning = parsed.get('reasoning', 'No reasoning provided')
                
                asyncio.run_coroutine_threadsafe(
                    self.broadcast({
                        'type': 'terminal',
                        'content': f'\n{"="*70}\n✓ TASK COMPLETED\n{"="*70}\n\n{reasoning}\n\n',
                        'style': 'success'
                    }),
                    asyncio.get_event_loop()
                )
                
                title, url = agent._get_page_context()
                asyncio.run_coroutine_threadsafe(
                    self.broadcast({
                        'type': 'terminal',
                        'content': f'Summary:\n  Steps: {agent.step_count}\n  API calls: {agent.api_calls_made}\n',
                        'style': 'info'
                    }),
                    asyncio.get_event_loop()
                )
                
                if title and url:
                    asyncio.run_coroutine_threadsafe(
                        self.broadcast({
                            'type': 'terminal',
                            'content': f'  Final page: {title}\n  Final URL: {url}\n\n',
                            'style': 'info'
                        }),
                        asyncio.get_event_loop()
                    )
                
                return
            
            command = parsed['command']
            reasoning = parsed.get('reasoning', 'No reasoning provided')
            
            # Broadcast to UI
            asyncio.run_coroutine_threadsafe(
                self.broadcast({
                    'type': 'command',
                    'step': agent.step_count,
                    'command': command,
                    'reasoning': reasoning
                }),
                asyncio.get_event_loop()
            )
            
            asyncio.run_coroutine_threadsafe(
                self.broadcast({
                    'type': 'terminal',
                    'content': f'\n--- Step {agent.step_count} ---\n',
                    'style': 'step'
                }),
                asyncio.get_event_loop()
            )
            
            asyncio.run_coroutine_threadsafe(
                self.broadcast({
                    'type': 'terminal',
                    'content': f'Reasoning: {reasoning}\n',
                    'style': 'reasoning'
                }),
                asyncio.get_event_loop()
            )
            
            asyncio.run_coroutine_threadsafe(
                self.broadcast({
                    'type': 'terminal',
                    'content': f'Command: {command}\n',
                    'style': 'command'
                }),
                asyncio.get_event_loop()
            )
            
            # Execute command using agent.py
            with self.agent_lock:
                result = agent._execute_command(command)
            
            if result.success:
                asyncio.run_coroutine_threadsafe(
                    self.broadcast({
                        'type': 'terminal',
                        'content': '✓ SUCCESS\n',
                        'style': 'success'
                    }),
                    asyncio.get_event_loop()
                )
                agent.consecutive_failures = 0
            else:
                asyncio.run_coroutine_threadsafe(
                    self.broadcast({
                        'type': 'terminal',
                        'content': '✗ FAILED\n',
                        'style': 'error'
                    }),
                    asyncio.get_event_loop()
                )
                agent.consecutive_failures += 1
            
            # Show output
            output_lines = result.output.split('\n')
            for line in output_lines[:20]:
                if line.strip():
                    asyncio.run_coroutine_threadsafe(
                        self.broadcast({
                            'type': 'terminal',
                            'content': f'  {line}\n',
                            'style': 'output'
                        }),
                        asyncio.get_event_loop()
                    )
            
            if len(output_lines) > 20:
                asyncio.run_coroutine_threadsafe(
                    self.broadcast({
                        'type': 'terminal',
                        'content': f'  ... ({len(output_lines) - 20} more lines)\n',
                        'style': 'output'
                    }),
                    asyncio.get_event_loop()
                )
            
            # Build feedback for next step
            feedback = agent._build_feedback(result, task)
            
            try:
                llm_response = agent._call_llm(feedback)
            except Exception as e:
                asyncio.run_coroutine_threadsafe(
                    self.broadcast({
                        'type': 'terminal',
                        'content': f'LLM Error: {e}\n',
                        'style': 'error'
                    }),
                    asyncio.get_event_loop()
                )
                break
        
        if agent.step_count >= max_steps:
            asyncio.run_coroutine_threadsafe(
                self.broadcast({
                    'type': 'terminal',
                    'content': f'\n{"="*70}\n⚠ Maximum steps reached ({max_steps})\n{"="*70}\n',
                    'style': 'warning'
                }),
                asyncio.get_event_loop()
            )
    
    async def send_message(self, ws: web.WebSocketResponse, message: Dict[str, Any]):
        """Send message to specific WebSocket."""
        try:
            await ws.send_json(message)
        except Exception as e:
            print(f"Error sending message: {e}")
    
    async def broadcast(self, message: Dict[str, Any]):
        """Broadcast message to all connected clients."""
        dead_sockets = set()
        
        for ws in self.websockets:
            try:
                await ws.send_json(message)
            except Exception:
                dead_sockets.add(ws)
        
        self.websockets -= dead_sockets
    
    async def on_shutdown(self, app):
        """Cleanup on shutdown."""
        await self.stop_streaming()
        if self.streamer:
            await self.streamer.close()
        if self.agent:
            self.agent.close()
    
    def run(self):
        """Start the server."""
        self.app.on_shutdown.append(self.on_shutdown)
        
        print(f"""
╔══════════════════════════════════════════════════════════╗
║     AI Browser Agent - Using agent.py                   ║
╚══════════════════════════════════════════════════════════╝

🌐 Server: http://{self.host}:{self.port}
📡 WebSocket: ws://{self.host}:{self.port}/ws
🎥 Live Feed: {self.fps} FPS
🤖 Agent: Full agent.py execution + reasoning

Press Ctrl+C to stop
        """)
        
        web.run_app(self.app, host=self.host, port=self.port, print=lambda x: None)


def main():
    """Entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description='AI Browser Agent UI Server')
    parser.add_argument('--host', default='localhost', help='Server host')
    parser.add_argument('--port', type=int, default=8080, help='Server port')
    parser.add_argument('--fps', type=int, default=20, help='Screenshot FPS')
    
    args = parser.parse_args()
    
    server = AgentUIServer(host=args.host, port=args.port)
    server.fps = args.fps
    server.frame_interval = 1.0 / args.fps
    
    try:
        server.run()
    except KeyboardInterrupt:
        print("\nShutting down...")


if __name__ == '__main__':
    main()