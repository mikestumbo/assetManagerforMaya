# Test Maya Threading Diagnostics
# Run this in Maya Script Editor (Python tab) to test threading

import threading
import time

print("🔍 Testing Maya threading diagnostics...")

def test_simple_thread():
    """Test basic threading without maya.utils"""
    print("📍 Simple thread started")
    time.sleep(2)
    print("📍 Simple thread finished")

def test_maya_deferred():
    """Test maya.utils.executeDeferred"""
    try:
        import maya.utils # type: ignore
        print("📍 About to test maya.utils.executeDeferred...")
        
        def callback():
            print("✅ maya.utils.executeDeferred callback executed!")
            
        maya.utils.executeDeferred(callback)
        print("📍 maya.utils.executeDeferred call made")
        
    except Exception as e:
        print(f"❌ maya.utils.executeDeferred failed: {e}")

def test_thread_with_deferred():
    """Test threading + maya.utils.executeDeferred"""
    def background_work():
        print("📍 Background thread started")
        time.sleep(1)
        
        try:
            import maya.utils # type: ignore
            print("📍 About to call executeDeferred from thread...")
            
            def ui_callback():
                print("✅ UI callback from background thread executed!")
                
            maya.utils.executeDeferred(ui_callback)
            print("📍 executeDeferred called from background thread")
            
        except Exception as e:
            print(f"❌ executeDeferred from thread failed: {e}")
    
    thread = threading.Thread(target=background_work, daemon=True)
    thread.start()
    print("📍 Background thread launched")

# Run tests
print("\n1️⃣ Testing simple thread...")
thread1 = threading.Thread(target=test_simple_thread, daemon=True)
thread1.start()

print("\n2️⃣ Testing maya.utils.executeDeferred...")
test_maya_deferred()

print("\n3️⃣ Testing thread + executeDeferred...")
test_thread_with_deferred()

print("\n✅ All tests launched. Check output above for results.")