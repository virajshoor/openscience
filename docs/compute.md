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