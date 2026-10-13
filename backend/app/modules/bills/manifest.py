"""Offline module inventory for ticket 01, not an active L01 registration.

The manifest has no runtime consumer yet: ticket 03 will expose the module through
its public registration point only after the real workflow can run. Empty
capabilities are intentional, not a callable stub or an authorization bypass.
"""
from app.contracts.platform import ModuleManifest

PRIVATE_TOOLS = ()
MANIFEST = ModuleManifest(
    module_name="bills",
    version="0.4.0",
    owner="zhouey314-cloud",
    description="账单私有计算；B08与公共模型已就绪，L01业务注册尚未完成",
    implementation_kind="workflow",
    capabilities=[],
    dependencies=[],
)
