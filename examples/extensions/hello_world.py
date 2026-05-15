"""Minimal JARVIS extension — registers a simple 'hello' tool.

Place this file in ``.jarvis/extensions/hello_world.py`` or
``~/.jarvis/extensions/hello_world.py`` and it will be loaded automatically.
"""

__version__ = "1.0.0"
__description__ = "Demo extension that registers a hello tool"


async def jarvis_extension(api):
    """Extension entry point — receives an ExtensionAPI instance."""

    # Register a tool with a simple class
    class HelloTool:
        name = "hello"
        description = "Say hello to someone"
        input_schema = {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Name to greet",
                }
            },
            "required": ["name"],
        }

        async def execute(self, input_data: dict) -> dict:
            name = input_data.get("name", "World")
            return {
                "success": True,
                "result": f"Hello, {name}!",
            }

    api.register_tool(HelloTool())
