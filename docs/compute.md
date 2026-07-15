# Compute Backends

OpenScience supports pluggable compute backends for executing commands and jobs.

## Local backend

Runs commands on the local machine via `asyncio.create_subprocess_exec`.

- Default backend, no configuration needed.
- Suitable for lightweight tools, API calls, and small scripts.

## SSH backend

Connects to a remote host via paramiko and executes commands remotely.

### Configuration

Configure via the Settings modal or the `/compute/ssh` endpoint:

```
POST /compute/ssh
{
  "host": "lab-box.university.edu",
  "user": "your-username",
  "port": 22,
  "key_path": "~/.ssh/id_rsa"
}
```

### Security

- Uses system known_hosts verification (`RejectPolicy`).
- Does NOT auto-accept unknown host keys.
- If a host key changes, the connection is rejected until you update your
  `~/.ssh/known_hosts`.

### Slurm wrappers

The SSH backend includes convenience methods for Slurm:

| Method | Description |
|--------|-------------|
| `submit_slurm(script)` | Write a script to /tmp and run `sbatch`. Returns job_id. |
| `slurm_status(job_id)` | Run `squeue -j {job_id}` and return the state. |
| `slurm_cancel(job_id)` | Run `scancel {job_id}`. |
| `upload(local, remote)` | SFTP put a file to the remote host. |
| `download(remote, local)` | SFTP get a file from the remote host. |

## Exposed as tools

Compute is exposed to the agent through tools (see [tools.md](./tools.md)):

- `compute.run` — run a shell command on the selected backend.
- `slurm.submit` / `slurm.status` / `slurm.cancel` — manage Slurm jobs on the
  SSH backend.

Select the backend per chat via the `compute` field on `POST /chat`:
`local`, `ssh`, or `slurm` (`slurm` uses the SSH transport and the Slurm tools).
The Settings modal exposes the same choice.

## Remote code execution (code.run over SSH)

`code.run` stages execution on the SSH backend: the script is SFTP-uploaded to
`/tmp/os_<run_id>_script.*`, executed with `MPLBACKEND=Agg` and a remote figure
directory, then any generated figures are SFTP-downloaded back into the local
run `outputs/` so they render in the UI and are content-addressed for
verification. Override the remote interpreter with `OS_REMOTE_PYTHON`.