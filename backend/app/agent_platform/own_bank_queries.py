"""Small public discovery entries over the existing audited bank read ports."""

from app.contracts.bank import QueryFailure
from app.contracts.common import OperationLevel, TaskStatus
from app.contracts.platform import CapabilityDefinition, ModuleManifest
from app.contracts.tasks import ModuleError, ModuleResult


def manifest(name):
    return ModuleManifest(module_name="transfer", version="0.4-own-queries-1", owner="Erwin",
        description=("查询当前登录本人账户及可用余额" if name == "list_accounts"
                     else "查询当前登录本人保存的收款联系人；只返回脱敏信息"),
        implementation_kind="workflow", dependencies=["bank_gateway", "security"],
        capabilities=[CapabilityDefinition(name="transfer." + name, input_schema_ref="StartTransferInput",
            output_schema_ref="ModuleResult[AccountList]" if name == "list_accounts" else "ModuleResult[PayeeList]",
            required_permissions=["transfer.read"], operation_level=OperationLevel.READ,
            side_effect=False, confirmation_policy="none", timeout_ms=4_000,
            retry_policy="read_only", handler_ref="agent_platform.own_bank_queries." + name)])


class OwnBankQuery:
    def __init__(self, name, ports):
        self.name, self.ports = name, ports

    def _read(self, trusted):
        # Neither model arguments nor user text select another person's identity.
        # B03 defines absent search as all saved contacts; an empty search object
        # is invalid at the bank and must not be manufactured as a filter.
        outcome = self.ports.read(trusted, "bank." + self.name,
                                  None if self.name == "list_payees" else {})
        bank_result = outcome.result
        ok = outcome.executed and bank_result is not None and not isinstance(bank_result, QueryFailure)
        return ModuleResult(task_id=trusted.task_id, run_id=trusted.run_id,
            status=TaskStatus.SUCCEEDED if ok else TaskStatus.FAILED,
            data=bank_result.data if ok else None,
            message=("已查到您的本人账户与可用余额。" if self.name == "list_accounts"
                     else "已查到您保存的收款联系人。") if ok else "暂时无法查询，请稍后重试。",
            interaction=None, error=None if ok else ModuleError(code="QUERY_UNAVAILABLE",
                source="platform", field=None, reason="本人信息读取未完成。", upstream_code=None),
            allowed_actions=[], recovery_required=False, recovery_reason=None)

    def start(self, trusted, request, *, thread_id=None):
        return self._read(trusted)

    def resume(self, trusted, response, *, thread_id=None):
        return self._read(trusted)

    def recover_session(self, trusted, *, source_session_id, thread_id=None):
        return self._read(trusted)

    def checkpoint_context(self, trusted, *, thread_id=None):
        return None


def register_own_bank_queries(runtime):
    for name in ("list_accounts", "list_payees"):
        def factory(trusted, saver, trace, name=name):
            # Reuse the audited/authorized read path; this entry never invokes
            # the workflow or its write/confirmation methods.
            ports = runtime._transfer_factory(trusted, saver, trace).ports
            return OwnBankQuery(name, ports)
        runtime.harness.registry.register_module(manifest(name), factory)
