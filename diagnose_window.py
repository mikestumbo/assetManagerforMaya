# Check Asset Manager Window State
# Run this in Maya Script Editor (Python tab) to diagnose the issue

print("🔍 Diagnosing Asset Manager window state...")

try:
    import maya_plugin
    
    if hasattr(maya_plugin, '_asset_manager_window') and maya_plugin._asset_manager_window:
        window = maya_plugin._asset_manager_window
        print("✅ Asset Manager window found")
        
        # Check progress bar state
        if hasattr(window, '_progress_bar'):
            progress_bar = window._progress_bar
            if progress_bar:
                is_visible = progress_bar.isVisible()
                print(f"📊 Progress bar visible: {is_visible}")
                
                # Force hide it
                progress_bar.setVisible(False)
                print("🔧 Progress bar hidden")
            else:
                print("⚠️ Progress bar is None")
        else:
            print("⚠️ No _progress_bar attribute")
        
        # Check status
        if hasattr(window, '_set_status'):
            window._set_status("Ready - Diagnostics Complete")
            print("✅ Status reset")
        else:
            print("⚠️ No _set_status method")
            
        # Check if there are any active threads
        import threading
        active_threads = threading.active_count()
        print(f"🧵 Active threads: {active_threads}")
        
        for thread in threading.enumerate():
            print(f"   - {thread.name}: {thread.is_alive()}")
            
    else:
        print("❌ Asset Manager window not found")
        
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()

print("✅ Diagnostics complete")