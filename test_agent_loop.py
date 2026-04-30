"""Quick smoke test for TUI import chain and agent loop flow."""
import asyncio
import traceback

async def main():
    errors = []
    
    # Test 1: core.config imports
    print("[1] Testing core.config import...")
    try:
        from core.config import Settings
        print("    OK: core.config.Settings imported")
    except Exception as e:
        errors.append(f"core.config import: {e}")
        print(f"    FAIL: {e}")
    
    # Test 2: Banner import
    print("[2] Testing Banner import...")
    try:
        from interface.textual_ui.widgets.banner.banner import Banner
        print("    OK: Banner imported")
    except Exception as e:
        errors.append(f"Banner import: {e}")
        print(f"    FAIL: {e}")
    
    # Test 3: app.py import
    print("[3] Testing app.py import...")
    try:
        from interface.textual_ui.app import run_textual_ui
        print("    OK: app.py imported")
    except Exception as e:
        errors.append(f"app import: {e}")
        print(f"    FAIL: {e}")
    
    # Test 4: AgentLoop creation
    print("[4] Testing AgentLoop creation...")
    try:
        from interface.textual_ui.agent_loop import AgentLoop
        from core.agents.coding_agent import CodingAgent
        from core.llm.sdk_adapter import SDKAdapter
        from core.llm_sdk.openai.sdk import OpenAISDK
        from core.tools.registry import ToolRegistry
        
        sdk = OpenAISDK(api_key="test")
        provider = SDKAdapter(sdk, "test")
        registry = ToolRegistry(provider, "gpt-4o")
        agent = CodingAgent(provider, registry, "gpt-4o")
        
        # Simulate tui_main Config
        from interface.textual_ui.tui_main import Config
        config = Config(model="gpt-4o", base_url=None, api_key="test", sdk="openai")
        
        loop = AgentLoop(agent=agent, config=config, tool_registry=registry)
        print("    OK: AgentLoop created")
        
        # Test that skill_manager works
        skills = loop.skill_manager.available_skills
        print(f"    OK: SkillManager has {len(skills)} skills")
        
        # Test that tool_manager works
        tools = loop.tool_manager.available_tools
        print(f"    OK: ToolManager has {len(tools)} tools")
        
    except Exception as e:
        errors.append(f"AgentLoop: {e}")
        traceback.print_exc()
    
    # Test 5: Banner.set_state with new signature
    print("[5] Testing Banner._build_state()...")
    try:
        from interface.textual_ui.widgets.banner.banner import Banner, BannerState
        state = Banner._build_state(config, loop.skill_manager)
        print(f"    OK: BannerState = {state}")
    except Exception as e:
        errors.append(f"Banner._build_state: {e}")
        traceback.print_exc()
    
    # Test 6: AgentLoop.act() flow
    print("[6] Testing AgentLoop.act() (expect API error)...")
    try:
        events = []
        async for event in loop.act("hello"):
            events.append(event)
            print(f"    Event: {type(event).__name__}: {str(event)[:100]}")
        print(f"    OK: Got {len(events)} events")
    except Exception as e:
        errors.append(f"AgentLoop.act: {e}")
        traceback.print_exc()
    
    # Summary
    print("\n" + "="*60)
    if errors:
        print(f"FAILED: {len(errors)} errors")
        for err in errors:
            print(f"  - {err}")
    else:
        print("ALL TESTS PASSED")

asyncio.run(main())
