# Examples

Runnable Docker Compose projects for the rusty-conduit family. Each one runs on its own: lab SSH servers, stand-in upstream proxies, and private services are part of the project. **Dev and testing only.**

| Example | Shows | Guide |
| :--- | :--- | :--- |
| [`direct/`](direct/compose.yaml) | `rusty-conduit` for your host and for other containers, with a blocklist and access logs | [Docker: basics §3](../docs/DOCKER-BASIC.md#3-a-proxy-for-your-host-and-your-other-containers) |
| [`switch/`](switch/) | `rusty-conduit-switch` rules, failover chains, `test-route`, and hot reload | [Docker: basics §5](../docs/DOCKER-BASIC.md#5-rule-based-routing-with-hot-reload) |
| [`egress-sandbox/`](egress-sandbox/compose.yaml) | A client on a network with no route out except an allowlisting proxy | [Docker: advanced §5](../docs/DOCKER-ADVANCED.md#5-an-egress-sandbox-network) |
| [`ssh-tunnel/`](ssh-tunnel/compose.yaml) | `rusty-conduit-ssh` into a private network, an `ssh -L` port forward, the reverse proxy, and reconnects | [Docker: advanced §2](../docs/DOCKER-ADVANCED.md#2-ssh-tunnels-in-containers) |
| [`scale-out/`](scale-out/) | HAProxy balancing N replicas, discovered through Docker DNS; `--scale` up and down | [Docker: advanced §4](../docs/DOCKER-ADVANCED.md#4-scale-out-with-haproxy-and-docker-dns) |
| [`homelab-stack/`](homelab-stack/) | Everything together: a switch pool routing to an egress pool and an SSH-tunnel pool behind one HAProxy, with optional MITM | [Docker: advanced §6](../docs/DOCKER-ADVANCED.md#6-the-homelab-stack) |

`lab/sshd/` is the lab SSH server image the SSH examples build. It stands in for your own bastion and is not for real use.

## Run one

```sh
cd examples/<example>
docker compose up -d --build     # --build only matters for the SSH examples
# … try the commands at the top of its compose.yaml …
docker compose down -v
```

The examples publish on `127.0.0.1` ports `3128`, `1080`, `8080`, and `8404`, so run one at a time.

## Test them all

```sh
examples/smoke-test.sh                 # every example
examples/smoke-test.sh scale-out       # just one
```

It needs Docker with Compose v2, `curl`, and internet access. Each example is brought up, checked, and removed with its volumes.
