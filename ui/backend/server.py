#!/usr/bin/env python3
"""
WebSocket server for AI Browser Agent UI
Fixed: Runs sync Playwright in thread pool executor
"""

import asyncio
import json
import os
import sys
import base64
from pathlib import Path
from typing import Set, Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor

try:
    from aiohttp import web
    import aiohttp_cors
except ImportError:
    print("Error: aiohttp required. Install with: pip install aiohttp aiohttp-cors")
    sys.exit(1)

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

try:
    from agent import LLMBrowserAgent
    from main import BrowserAgent
except ImportError as e:
    print(f"Error importing agent modules: {e}")
    sys.exit(1)


class AgentUIServer:
    """WebSocket server managing agent execution and UI updates."""
    
    def __init__(self, host: str = "localhost", port: int = 8080):
        self.host = host
        self.port = port
        self.app = web.Application()
        self.websockets: Set[web.WebSocketResponse] = set()
        
        self.agent: Optional[LLMBrowserAgent] = None
        self.browser: Optional[BrowserAgent] = None
        self.task_running = False
        
        # Thread pool for running sync Playwright code
        self.executor = ThreadPoolExecutor(max_workers=1)
        
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
            'ready': True
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
    
    def _init_browser_sync(self, config: Dict[str, Any]) -> tuple:
        """Initialize browser synchronously in thread pool."""
        try:
            browser = BrowserAgent(headless=False)
            api_key = config.get('api_key') or os.getenv('GROQ_API_KEY')
            model = config.get('model', 'llama-3.1-8b-instant')
            
            agent = LLMBrowserAgent(
                api_key=api_key,
                headless=False,
                model=model,
                browser_agent=browser
            )
            return agent, browser, None
        except Exception as e:
            return None, None, str(e)
    
    async def initialize_agent(self, config: Dict[str, Any]):
        """Initialize the browser agent in thread pool."""
        try:
            await self.broadcast({
                'type': 'terminal',
                'content': 'Initializing browser agent...\n',
                'style': 'info'
            })
            
            # Run initialization in thread pool
            loop = asyncio.get_event_loop()
            agent, browser, error = await loop.run_in_executor(
                self.executor,
                self._init_browser_sync,
                config
            )
            
            if error:
                await self.broadcast({
                    'type': 'terminal',
                    'content': f'✗ Initialization failed: {error}\n',
                    'style': 'error'
                })
                return
            
            self.agent = agent
            self.browser = browser
            
            await self.broadcast({
                'type': 'terminal',
                'content': '✓ Agent initialized successfully\n',
                'style': 'success'
            })
            await self.broadcast({
                'type': 'status',
                'ready': True,
                'message': 'Agent ready'
            })
        
        except Exception as e:
            await self.broadcast({
                'type': 'terminal',
                'content': f'✗ Initialization failed: {str(e)}\n',
                'style': 'error'
            })
    
    async def execute_task(self, task: str):
        """Execute agent task with real-time updates."""
        if not self.agent:
            await self.broadcast({
                'type': 'error',
                'message': 'Agent not initialized. Please refresh and try again.'
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
        
        # Start screenshot loop
        screenshot_task = asyncio.create_task(self.screenshot_loop())
        
        try:
            # Execute task in thread pool
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                self.executor,
                self._execute_task_sync,
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
            screenshot_task.cancel()
            try:
                await screenshot_task
            except asyncio.CancelledError:
                pass
    
    def _execute_task_sync(self, task: str):
        """Synchronous task execution (runs in thread pool)."""
        agent = self.agent
        max_steps = agent.DEFAULT_MAX_STEPS
        
        agent.step_count = 0
        agent.conversation_history = []
        agent.api_calls_made = 0
        agent.consecutive_failures = 0
        
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
        
        while agent.step_count < max_steps and self.task_running:
            agent.step_count += 1
            
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
    
    def run(self):
        """Start the server."""
        print(f"""
╔══════════════════════════════════════════════════════════╗
║          AI Browser Agent UI Server                      ║
╚══════════════════════════════════════════════════════════╝

🌐 Server running at: http://{self.host}:{self.port}
📡 WebSocket endpoint: ws://{self.host}:{self.port}/ws

Press Ctrl+C to stop
        """)
        
        web.run_app(self.app, host=self.host, port=self.port)


def main():
    """Entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description='AI Browser Agent UI Server')
    parser.add_argument('--host', default='localhost', help='Server host')
    parser.add_argument('--port', type=int, default=8080, help='Server port')
    
    args = parser.parse_args()
    
    server = AgentUIServer(host=args.host, port=args.port)
    
    try:
        server.run()
    except KeyboardInterrupt:
        print("\nShutting down...")


if __name__ == '__main__':
    main()