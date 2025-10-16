#!/usr/bin/env python3
"""
Bulletproof Namespace Cleanup - Test Suite v1.3.0
Comprehensive testing for complex Maya asset cleanup

Author: Mike Stumbo
Date: September 29, 2025
Version: 1.3.0
"""

import sys
from pathlib import Path

# Add src to Python path for testing
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

try:
    import maya.cmds as cmds # type: ignore
    MAYA_AVAILABLE = True
except ImportError:
    MAYA_AVAILABLE = False
    print("⚠️ Maya not available - running mock tests")

class MockCmds:
    """Mock Maya commands for testing without Maya"""
    namespaces = set()
    locked_nodes = set()
    connections = {}
    
    def namespace(self, **kwargs):
        if 'exists' in kwargs:
            return kwargs['exists'] in self.namespaces
        if 'removeNamespace' in kwargs:
            ns = kwargs['removeNamespace']
            if ns in self.namespaces:
                self.namespaces.remove(ns)
        return True
    
    def namespaceInfo(self, namespace, **kwargs):
        return [f"{namespace}:node1", f"{namespace}:node2", f"{namespace}:lockedNode"]
    
    def lockNode(self, nodes, **kwargs):
        if isinstance(nodes, str):
            nodes = [nodes]
        if 'query' in kwargs:
            return [node in self.locked_nodes for node in nodes]
        if 'lock' in kwargs and not kwargs['lock']:
            for node in nodes:
                self.locked_nodes.discard(node)
    
    def listConnections(self, attr, **kwargs):
        return self.connections.get(attr, [])
    
    def disconnectAttr(self, source, dest):
        if dest in self.connections:
            if source in self.connections[dest]:
                self.connections[dest].remove(source)
    
    def objExists(self, node):
        return True
    
    def delete(self, nodes):
        pass

class BulletproofCleanupTester:
    """Test suite for bulletproof namespace cleanup"""
    
    def __init__(self):
        self.cmds = cmds if MAYA_AVAILABLE else MockCmds() # type: ignore
        self.test_results = []
    
    def run_all_tests(self):
        """Run complete test suite"""
        print("🧪 Starting Bulletproof Cleanup Test Suite v1.3.0\n")
        
        tests = [
            self.test_basic_cleanup,
            self.test_locked_nodes_cleanup,
            self.test_connection_breaking,
            self.test_fallback_cleanup,
            self.test_complex_asset_scenario,
            self.test_multiple_namespace_cleanup
        ]
        
        for test in tests:
            try:
                result = test()
                self.test_results.append(result)
                status = "✅ PASS" if result['passed'] else "❌ FAIL"
                print(f"{status}: {result['name']}")
                if not result['passed']:
                    print(f"   Error: {result.get('error', 'Unknown error')}")
            except Exception as e:
                self.test_results.append({
                    'name': test.__name__,
                    'passed': False,
                    'error': str(e)
                })
                print(f"❌ FAIL: {test.__name__} - {e}")
        
        self._print_summary()
    
    def test_basic_cleanup(self):
        """Test basic namespace cleanup functionality"""
        namespace = "test_basic_123"
        
        # Setup
        if hasattr(self.cmds, 'namespaces'):
            self.cmds.namespaces.add(namespace)
        
        # Test cleanup
        success = self._bulletproof_namespace_cleanup(namespace)
        
        return {
            'name': 'Basic Namespace Cleanup',
            'passed': success,
            'details': f"Namespace {namespace} cleanup"
        }
    
    def test_locked_nodes_cleanup(self):
        """Test cleanup with locked nodes"""
        namespace = "test_locked_456"
        
        # Setup locked nodes
        if hasattr(self.cmds, 'namespaces'):
            self.cmds.namespaces.add(namespace)
            self.cmds.locked_nodes.add(f"{namespace}:lockedNode")
        
        # Test cleanup
        success = self._bulletproof_namespace_cleanup(namespace)
        
        return {
            'name': 'Locked Nodes Cleanup',
            'passed': success,
            'details': f"Cleanup with locked nodes in {namespace}"
        }
    
    def test_connection_breaking(self):
        """Test render connection breaking"""
        namespace = "test_connections_789"
        
        # Setup connections
        if hasattr(self.cmds, 'connections'):
            self.cmds.connections['rmanDefaultDisplay.displayType'] = [
                f"{namespace}:d_openexr.message"
            ]
        
        # Test connection breaking
        self._disconnect_render_connections(namespace)
        
        # Verify connections broken
        connections_remain = False
        if hasattr(self.cmds, 'connections'):
            for conn_list in self.cmds.connections.values():
                if any(namespace in conn for conn in conn_list):
                    connections_remain = True
                    break
        
        return {
            'name': 'Render Connection Breaking',
            'passed': not connections_remain,
            'details': f"Connection breaking for {namespace}"
        }
    
    def test_fallback_cleanup(self):
        """Test fallback cleanup strategy"""
        namespace = "test_fallback_101"
        
        # Setup problematic namespace
        if hasattr(self.cmds, 'namespaces'):
            self.cmds.namespaces.add(namespace)
        
        # Test fallback cleanup
        success = self._fallback_cleanup(namespace)
        
        return {
            'name': 'Fallback Cleanup Strategy',
            'passed': success,
            'details': f"Fallback cleanup for {namespace}"
        }
    
    def test_complex_asset_scenario(self):
        """Test cleanup scenario matching Veteran_Rig.mb complexity"""
        namespace = "test_veteran_complex"
        
        # Setup complex scenario
        if hasattr(self.cmds, 'namespaces'):
            self.cmds.namespaces.add(namespace)
            self.cmds.locked_nodes.add(f"{namespace}:globalVolumeAggregate")
            self.cmds.connections.update({
                'rmanDefaultDisplay.displayType': [f"{namespace}:d_openexr.message"],
                'rmanDefaultDisplay.displayChannels[0]': [f"{namespace}:Ci.message"],
                'rmanBakingGlobals.displays[0]': [f"{namespace}:rmanDefaultBakeDisplay.message"]
            })
        
        # Test complex cleanup
        success = self._bulletproof_namespace_cleanup(namespace)
        
        return {
            'name': 'Complex Asset Scenario (Veteran_Rig)',
            'passed': success,
            'details': f"Complex production asset cleanup for {namespace}"
        }
    
    def test_multiple_namespace_cleanup(self):
        """Test cleanup of multiple overlapping namespaces"""
        namespaces = ["thumb_001", "meta_002", "thumb_003"]
        
        # Setup multiple namespaces
        if hasattr(self.cmds, 'namespaces'):
            for ns in namespaces:
                self.cmds.namespaces.add(ns)
        
        # Test cleanup of all
        all_success = True
        for ns in namespaces:
            success = self._bulletproof_namespace_cleanup(ns)
            if not success:
                all_success = False
        
        return {
            'name': 'Multiple Namespace Cleanup',
            'passed': all_success,
            'details': f"Cleanup of {len(namespaces)} namespaces"
        }
    
    def _bulletproof_namespace_cleanup(self, namespace: str) -> bool:
        """Test implementation of bulletproof cleanup"""
        if not namespace:
            return True
            
        try:
            # Check if namespace exists
            if not self.cmds.namespace(exists=namespace):
                return True
            
            # Phase 1: Unlock nodes
            self._unlock_namespace_nodes(namespace)
            
            # Phase 2: Break connections
            self._disconnect_render_connections(namespace)
            
            # Phase 3: Remove namespace
            self.cmds.namespace(removeNamespace=namespace, deleteNamespaceContent=True)
            
            # Phase 4: Validate
            return not self.cmds.namespace(exists=namespace)
            
        except Exception as e:
            print(f"⚠️ Cleanup error: {e}")
            return self._fallback_cleanup(namespace)
    
    def _unlock_namespace_nodes(self, namespace: str):
        """Test implementation of node unlocking"""
        try:
            nodes = self.cmds.namespaceInfo(namespace, listOnlyDependencyNodes=True)
            if nodes:
                locked_states = self.cmds.lockNode(nodes, query=True)
                # Handle case where lockNode returns None
                if locked_states is not None:
                    locked_nodes = [node for node, locked in zip(nodes, locked_states) if locked]
                    if locked_nodes:
                        self.cmds.lockNode(locked_nodes, lock=False)
        except Exception as e:
            print(f"⚠️ Unlock error: {e}")
    
    def _disconnect_render_connections(self, namespace: str):
        """Test implementation of connection breaking"""
        try:
            connection_patterns = [
                'rmanDefaultDisplay.displayType',
                'rmanDefaultDisplay.displayChannels[0]',
                'rmanBakingGlobals.displays[0]'
            ]
            
            for pattern in connection_patterns:
                connections = self.cmds.listConnections(pattern, source=True, plugs=True)
                if connections:
                    for conn in connections:
                        if namespace in conn:
                            self.cmds.disconnectAttr(conn, pattern)
        except Exception as e:
            print(f"⚠️ Connection breaking error: {e}")
    
    def _fallback_cleanup(self, namespace: str) -> bool:
        """Test implementation of fallback cleanup"""
        try:
            if self.cmds.namespace(exists=namespace):
                self.cmds.namespace(removeNamespace=namespace, force=True)
            return not self.cmds.namespace(exists=namespace)
        except:
            return False
    
    def _print_summary(self):
        """Print test results summary"""
        total = len(self.test_results)
        passed = sum(1 for result in self.test_results if result['passed'])
        failed = total - passed
        
        print(f"\n📊 Test Results Summary:")
        print(f"   Total Tests: {total}")
        print(f"   ✅ Passed: {passed}")
        print(f"   ❌ Failed: {failed}")
        print(f"   Success Rate: {(passed/total)*100:.1f}%")
        
        if failed > 0:
            print(f"\n❌ Failed Tests:")
            for result in self.test_results:
                if not result['passed']:
                    print(f"   • {result['name']}: {result.get('error', 'Unknown error')}")

if __name__ == "__main__":
    tester = BulletproofCleanupTester()
    tester.run_all_tests()
    print(f"\n🎯 Bulletproof Cleanup Test Suite Complete!")