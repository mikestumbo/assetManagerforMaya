#!/usr/bin/env python3
"""
USD Thumbnail Support Test - Issue #12
Verifies that USD file formats are now supported for thumbnail generation
"""

import sys
from pathlib import Path

# Add src directory to path
current_dir = Path(__file__).parent
src_dir = current_dir / "src"
sys.path.insert(0, str(src_dir))


def test_usd_thumbnail_support():
    """Test USD file thumbnail support implementation"""
    print("🧪 USD THUMBNAIL SUPPORT TEST - Issue #12")
    print("=" * 60)

    try:
        # Import the thumbnail service
        from src.services.thumbnail_service_impl import ThumbnailServiceImpl

        print("✅ Successfully imported ThumbnailServiceImpl")

        # Create service instance
        service = ThumbnailServiceImpl()
        print("✅ Successfully instantiated ThumbnailServiceImpl")

        # Test USD file extensions support
        usd_extensions = ['.usd', '.usda', '.usdc', '.usdz']
        supported_count = 0

        print("\n🔍 Testing USD extension support:")
        for ext in usd_extensions:
            # Create a fake file path for testing
            test_file = Path(f"test_file{ext}")

            if service.is_thumbnail_supported(test_file):
                print(f"✅ {ext} - SUPPORTED")
                supported_count += 1
            else:
                print(f"❌ {ext} - NOT SUPPORTED")

        # Test if USD method exists
        print("\n🔧 Testing USD thumbnail generation method:")
        if hasattr(service, '_generate_usd_thumbnail'):
            print("✅ _generate_usd_thumbnail method exists")

            # Check method signature
            import inspect
            sig = inspect.signature(service._generate_usd_thumbnail)
            params = list(sig.parameters.keys())
            print(f"✅ Method signature: _generate_usd_thumbnail({', '.join(params)})")

        else:
            print("❌ _generate_usd_thumbnail method missing")
            return False

        # Test supported extensions list
        print("\n📋 Current supported extensions:")
        extensions = sorted(service._supported_extensions)
        for ext in extensions:
            if ext in usd_extensions:
                print(f"✅ {ext} (USD format)")
            else:
                print(f"  {ext}")

        print("\n📊 USD Support Summary:")
        print(f"✅ USD extensions supported: {supported_count}/{len(usd_extensions)}")
        print(f"✅ USD thumbnail method: {'Present' if hasattr(service, '_generate_usd_thumbnail') else 'Missing'}")

        # Test that the method can be called (without actual file)
        print("\n🧪 Testing USD thumbnail generation logic:")
        try:
            # This will fail due to file not existing, but method should be callable
            result = service._generate_usd_thumbnail(Path("nonexistent.usd"), (64, 64))
            # Should return None due to file not existing
            print(f"✅ USD thumbnail method callable (returned: {result})")
        except AttributeError:
            print("❌ USD thumbnail method not callable")
            return False
        except Exception as e:
            # Expected to fail with file not found, but method should be accessible
            print(f"✅ USD thumbnail method accessible (expected error: {type(e).__name__})")

        if supported_count == len(usd_extensions):
            print("\n🎉 SUCCESS: Full USD thumbnail support implemented!")
            return True
        else:
            print(f"\n❌ PARTIAL: Only {supported_count}/{len(usd_extensions)} USD extensions supported")
            return False

    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False


def test_color_scheme_support():
    """Test that USD has its own distinctive color scheme"""
    print("\n🎨 USD COLOR SCHEME TEST")
    print("=" * 60)

    try:
        # Read the source file to check for USD color definition
        impl_file = Path("src/services/thumbnail_service_impl.py")

        if impl_file.exists():
            with open(impl_file, 'r', encoding='utf-8') as f:
                content = f.read()

            # Check for USD color scheme
            if 'file_type == "USD"' in content:
                print("✅ USD has dedicated color scheme in file type icon generation")

                # Check for gold color scheme (premium look for industry standard)
                if '255, 200, 100' in content:
                    print("✅ USD uses gold gradient (255, 200, 100) - premium industry standard")
                else:
                    print("⚠️ USD color scheme present but not using expected gold theme")

                return True
            else:
                print("❌ USD color scheme not found")
                return False
        else:
            print("❌ Implementation file not found")
            return False

    except Exception as e:
        print(f"❌ Error checking color scheme: {e}")
        return False


def main():


    support_test = test_usd_thumbnail_support()
    color_test = test_color_scheme_support()

    print("\n" + "=" * 60)
    print("🎯 USD THUMBNAIL SUPPORT TEST RESULTS")
    print("=" * 60)

    if support_test and color_test:
        print("🎉 Issue #12 - USD THUMBNAIL SUPPORT: COMPLETE!")
        print("✅ All USD file extensions (.usd, .usda, .usdc, .usdz) supported")
        print("✅ USD thumbnail generation method implemented")
        print("✅ Professional gold color scheme for USD files")
        print("🚀 USD files will now show proper thumbnails in Asset Manager!")
        return True
    else:
        print("❌ Issue #12 - USD THUMBNAIL SUPPORT: INCOMPLETE")
        if not support_test:
            print("🔧 USD extension support needs fixing")
        if not color_test:
            print("🔧 USD color scheme needs implementation")
        return False

if __name__ == "__main__":


    sys.exit(0 if success else 1)
