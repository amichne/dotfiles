# Disposable container

Use the same Docker image and command on a local computer or a cloud worker.
The runner copies Git-selected public files into a new container.
It never mounts the host HOME, source directory, Docker socket, or credential files.

## Local use

Install Docker, uv 0.12.9, and Python 3.12 or 3.13.
Start the Docker runtime before these commands.
On macOS with Colima, use `colima start`.

From the repository root, run:

```sh
uv run --locked --script scripts/sandbox.py check
```

The command prepares the dependency image and runs `./scripts/check.sh` inside a disposable container.
The command returns the gate's exit status.
The runner removes the container after success, failure, or an interrupt.
The dependency image stays in Docker's cache for later runs.

To prepare the image without a test run, use:

```sh
uv run --locked --script scripts/sandbox.py build
```

For a disposable shell, use:

```sh
uv run --locked --script scripts/sandbox.py shell
```

For a specific command, use:

```sh
uv run --locked --script scripts/sandbox.py run -- /bin/sh -c 'exit 42'
```

This example returns status 42 and removes its container.
Changes inside the container disappear after each run.
The source snapshot includes public edits and public files that Git does not yet track.
Ignored files stay outside the snapshot, even when Git tracks them.
The runner rejects selected symlinks and non-file entries before Docker starts.

To examine the snapshot without Docker, use a new output path:

```sh
uv run --locked --script scripts/sandbox.py snapshot /tmp/dotfiles-source.tar
tar -tf /tmp/dotfiles-source.tar
```

The runner rejects an existing output file.
The `--source PATH` option selects a different source root, including a HOME with `.dotfiles.git`.
The snapshot contains source files alone.
A new Git index inside the container supplies the gate's repository context.

## Hosted CI

`.github/workflows/sandbox.yml` runs the same container gate on GitHub's Ubuntu 24.04 workers.
It runs for pull requests, pushes to `main`, and manual requests.
The workflow pins each action by commit and uses read-only repository access.
The container receives no host credentials.

## Native engineering fixtures

The separate `Native engineering fixtures` job runs `tests/native-agent-hosts.mjs`.
It pins Pi 1.3.0, Codex 0.163.0, Vale 3.24.0, and the Slopsentral source revision.
The fixtures use disposable HOME directories and fixed local responses.
They spend no paid model inference.
They examine native instruction selection, override precedence, hook trust, and failure reports.
They also run strict TypeScript analysis against the Pi declarations.

For a local run, supply these paths in environment variables:

| Variable | Path |
| --- | --- |
| `PYTHON_BIN` | Python 3.12 or 3.13 executable |
| `UV_BIN` | uv 0.12.9 executable |
| `VALE_BIN` | Vale 3.24.0 executable |
| `ENGINEERING_SLOPSENTRAL_ROOT` | Slopsentral checkout |
| `CODEX_BIN` | Codex 0.163.0 executable |
| `PI_SDK_ROOT` | Pi 1.3.0 package directory |
| `TYPESCRIPT_ROOT` | TypeScript 7.0.2 package directory, near `@types/node` |

```sh
node --test tests/native-agent-hosts.mjs
```

Missing dependencies fail this command. They do not produce skipped coverage.
The Codex fixture needs a loopback socket for its fixed response server.
The [native engineering guide](https://slopsentral.michne.com/guides/engineering-baseline)
states the difference between native completion and a passing handoff check.

## Cloud use

Select `amichne/dotfiles` as the environment's repository.
Keep the environment private and supply no secrets.
Use a worker with Docker, uv 0.12.9, and Python 3.12 or 3.13.

Use this install command from the repository root:

```sh
uv run --locked --script scripts/sandbox.py build
```

Use this command for each task:

```sh
uv run --locked --script scripts/sandbox.py check
```

The same files control local and cloud runs.
The image build needs network access for Docker registries, Debian packages, Python, and PyPI.
When a managed worker supplies `CODEX_PROXY_CERT`, the runner passes that certificate as a BuildKit secret.
Each uv download uses that certificate without a permanent copy in the image.
The test container has no network access.
Use a cloud checkout that contains `containers/Dockerfile` and `scripts/sandbox.py`.

[Codex Cloud environments](https://learn.chatgpt.com/docs/environments/cloud-environments) describes installation, private access, and publication.
Publication and a successful task from that environment establish cloud execution.
A local container result alone does not establish cloud execution.

## Scope and limits

`containers/Dockerfile` pins the Node and uv images by digest.
It selects Python 3.12.14 and installs the project's locked dependencies.
Debian packages follow the package repository at image-build time.
The runner prints the exact image ID and source digest for each run.
Docker selects the machine's native architecture.
Local ARM64 results do not establish AMD64 results.

The container uses UID 10001, a read-only root, no Linux capabilities, and disposable writable directories.
Docker limits each container to two CPUs, 2 GiB of memory, and 256 processes.
The runtime tests examine these protections, network isolation, and the fresh Git index.
They skip outside the container.

The gate exercises the bare-HOME manager, shell startup, prompt logic, syntax, types, data files, and documentation.
Shell fixtures supply bounded substitutes for external integrations.
This setup does not establish macOS behavior, real service access, or a complete interactive desktop session.
Container isolation also depends on Docker and the host kernel.

If the host process receives SIGKILL or loses power, cleanup cannot run.
To find containers that need removal, use:

```sh
docker ps -a --filter label=amichne.dotfiles.sandbox=true
```

After review, remove a named container with `docker rm --force CONTAINER`.
