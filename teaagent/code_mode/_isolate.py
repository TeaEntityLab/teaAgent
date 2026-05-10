from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from ._container import ContainerCodeModeBackend
from ._types import CodeModeResult, CodeModeSandbox

_GVISOR_OCI_RUNTIME = 'runsc'


@dataclass(frozen=True)
class IsolateCodeModeBackend:
    """VM-level isolation backend using gVisor (runsc) OCI runtime.

    All syscalls are intercepted by the gVisor sandbox kernel, providing
    stronger isolation than seccomp/AppArmor alone. Requires the gVisor
    runtime (runsc) to be installed and registered with the container daemon.

    Uses stricter defaults than ContainerCodeModeBackend: image digest
    required by default and seccomp profile set to 'default'.
    """

    image: str
    runtime: str = 'docker'
    python_executable: str = 'python3'
    network: str = 'none'
    cpus: float = 1.0
    user: str = '65534:65534'
    tmpfs_size_mb: int = 16
    require_image_digest: bool = True
    allowed_images: Optional[frozenset[str]] = None
    seccomp_profile: Optional[str] = 'default'
    apparmor_profile: Optional[str] = None
    selinux_label: Optional[str] = None

    @property
    def is_vm_isolated(self) -> bool:
        return True

    def execute(
        self,
        code: str,
        inputs: dict[str, Any],
        sandbox: CodeModeSandbox,
    ) -> CodeModeResult:
        backend = ContainerCodeModeBackend(
            image=self.image,
            runtime=self.runtime,
            python_executable=self.python_executable,
            network=self.network,
            cpus=self.cpus,
            user=self.user,
            tmpfs_size_mb=self.tmpfs_size_mb,
            require_image_digest=self.require_image_digest,
            allowed_images=self.allowed_images,
            seccomp_profile=self.seccomp_profile,
            apparmor_profile=self.apparmor_profile,
            selinux_label=self.selinux_label,
            oci_runtime=_GVISOR_OCI_RUNTIME,
        )
        return backend.execute(code, inputs, sandbox)
