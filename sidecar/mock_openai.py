"""Mock OpenAI-compatible endpoint for end-to-end testing.

Returns a fixed response: first a tool_call to uniprot.fetch, then a final
assistant message summarizing the result. Run with: python mock_openai.py
"""

import json
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer


class Handler(BaseHTTPRequestHandler):
    call_count = 0

    def do_POST(self):
        if not self.path.endswith("/chat/completions"):
            self.send_error(404)
            return
        body = json.loads(self.rfile.read(int(self.headers.get("content-length", 0))))
        msgs = body.get("messages", [])
        stream = body.get("stream", False)

        # If the last message is a tool result, give the final answer
        last = msgs[-1] if msgs else {}
        if last.get("role") == "tool":
            payload = {
                "choices": [{
                    "delta": {"content": "Done — fetched the UniProt entry and rendered the structure."},
                    "finish_reason": "stop",
                }],
            }
        elif "tools" in body:
            # Native tool-calling mode — emit a tool_call
            payload = {
                "choices": [{
                    "delta": {
                        "tool_calls": [{
                            "index": 0,
                            "id": "call_1",
                            "type": "function",
                            "function": {
                                "name": "pdb_fetch",
                                "arguments": json.dumps({"pdb_id": "1CRN"}),
                            },
                        }],
                    },
                    "finish_reason": "tool_calls",
                }],
            }
        else:
            # No tools in request → respond with ReAct text instead
            payload = {
                "choices": [{
                    "delta": {
                        "content": (
                            "Thought: I should fetch the PDB structure.\n"
                            'Action: ```json\n{"tool": "pdb_fetch", "input": {"pdb_id": "1CRN"}}\n```'
                        ),
                    },
                    "finish_reason": "stop",
                }],
            }

        if stream:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.end_headers()
            self.wfile.write(b"data: " + json.dumps(payload).encode() + b"\n\n")
            self.wfile.write(b"data: [DONE]\n\n")
            self.wfile.flush()
        else:
            # Non-streaming: synthesize a full message
            choice = payload["choices"][0]["delta"]
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({
                "choices": [{
                    "message": {
                        "role": "assistant",
                        "content": choice.get("content", ""),
                        "tool_calls": choice.get("tool_calls"),
                    },
                    "finish_reason": choice.get("finish_reason", "stop"),
                }],
            }).encode())

    def log_message(self, *args, **kwargs):
        pass


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 7120
    print(f"mock OpenAI listening on http://127.0.0.1:{port}", file=sys.stderr)
    HTTPServer(("127.0.0.1", port), Handler).serve_forever()
