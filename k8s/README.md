# k8s — laiive on k3s (D19)

Kustomize base + overlays. The deploy target is **one Hetzner CX32 running k3s**
(4 vCPU / 8 GB, Falkenstein). The manifests avoid anything k3s-specific in `base/`
so a managed cluster later is an overlay swap, not a rewrite.

The SPA is **not** in here — it stays on Cloudflare Pages (D18). Only the gateway
is publicly reachable; the retriever, pusher, search and Redis are namespace-internal.

```
base/                 namespace, config, the five workloads, six NetworkPolicies
overlays/prod/        ingress + TLS + real CORS origins + SOPS secret
overlays/local/       one replica each, NodePort, no ingress, plaintext secret
overlays/prod/traefik-config.yaml   NOT kustomized — goes on the node (see below)
scripts/env-to-secret.sh            root .env -> overlay secret
```

## Layout decisions worth knowing

**Config comes from a flat env map, exactly like the root `.env`.** Non-secret keys
live in `base/configmap.yaml` where they are readable in a diff; secrets come from a
generated `laiive-env` Secret. Both are consumed with `envFrom`, and pydantic-settings
and the gateway's dotenv loader both prefer process env, so the services need no
code change. `../../.env` never resolved inside the images anyway.

**The Secret name is hashed** (Kustomize's default). That is deliberate: rotating a
key changes the Secret name, which changes the pod spec, which rolls the pods.
Without it a rotation would sit unused until some unrelated deploy.

**Resource sizing fits 8 GB with room to spare.** k3s + Traefik + CoreDNS +
metrics-server + local-path ≈ 1.0 GB, cert-manager ≈ 150 Mi, workload requests
≈ 1.65 GB steady and ≈ 2.5 GB at the HPA ceiling — about 3.7 GB worst case. The
headroom is the point: a node with none OOMs during a rollout, when N+1 of
everything runs briefly. CPU limits are oversubscribed on purpose because the
workload is I/O-bound.

**One process per pod, no `--workers`.** Every retriever request path blocks in
the Starlette threadpool (`/chat` is `def`, `/chat/stream` yields from a sync
generator on purpose), so per-pod concurrency is bounded by anyio's 40 threadpool
tokens, not CPU. Workers would multiply memory for a bottleneck that is network
wait, and give one liveness probe for N processes.

## The security boundary

Two independent layers. Either one alone would be a real control; together, a
mistake in one is not an opening.

1. **NetworkPolicy** (`base/networkpolicies.yaml`) — default-deny, then explicit
   allows: Traefik→gateway, gateway→services, gateway/pusher/search→Redis, all→DNS,
   and egress to the internet **with the pod and service CIDRs excepted**. That
   `except:` is load-bearing; without it the egress rule re-permits all east-west
   traffic and the namespace is not default-deny at all.
   k3s enforces this on a default install (embedded kube-router) — do not start the
   server with `--disable-network-policy`.
2. **A shared internal key** (`laiive_shared/internal_auth.py`) — the gateway injects
   `X-Internal-Key`, each service verifies it with `hmac.compare_digest`, and the
   gateway strips any client-supplied copy in the same place it strips
   `X-User-Id`. Probes are exempt because the kubelet cannot authenticate. An unset
   key is a no-op, which is what keeps local runs and the test suites unchanged.

CORS is not part of this and cannot be: it is enforced by browsers, and the
gateway is not a browser.

## First deploy

```bash
# 1. secrets: generates INTERNAL_API_KEY into .env if absent, then encrypts
./k8s/scripts/env-to-secret.sh prod          # needs sops + an age key

# 2. Traefik timeouts and client-IP preservation — on the node, not via kubectl
scp k8s/overlays/prod/traefik-config.yaml \
    node:/var/lib/rancher/k3s/server/manifests/traefik-config.yaml

# 3. cert-manager, then the stack
kubectl apply -f https://github.com/cert-manager/cert-manager/releases/latest/download/cert-manager.yaml
kubectl apply -k k8s/overlays/prod
kubectl -n laiive rollout status deploy/gateway deploy/retriever deploy/pusher deploy/search
```

Before the first apply, replace `<tld>` in `overlays/prod/ingress.yaml` and
`overlays/prod/patches/cors.yaml`, and leave the Ingress on
`letsencrypt-staging` until a cert issues — production ACME allows five
certificates per week and DNS usually takes more tries than that.

`traefik-config.yaml` is not optional polish. `idleTimeout` defaults to 180s and a
city sweep is a single request that stays silent for 2–6 minutes, driven over this
ingress by Prefect Cloud from outside the cluster. `externalTrafficPolicy: Local`
is what makes the gateway's `trustProxy: 1` meaningful; without it every anonymous
user shares one rate-limit bucket.

## Local

```bash
./k8s/scripts/env-to-secret.sh local     # plaintext, gitignored
docker compose build                     # tags laiive-<svc>:latest
kubectl apply -k k8s/overlays/local      # gateway on :30800
```

`docker-compose.yml` is the other local path and covers the same topology with the
same images and probes. Together they stand in for a staging environment — a second
namespace on the single prod node would share its failure domain and prove little.

## Verifying the boundary

Both layers must be shown to fail closed **independently**; testing them together
only proves that at least one works.

```bash
# NetworkPolicy: a pod that is not the gateway cannot even connect
kubectl -n laiive run probe --rm -it --image=curlimages/curl --restart=Never -- \
  curl -m 5 http://retriever:8002/chat          # expect: timeout, not "refused"

# internal key: same request from a pod labelled app=gateway
kubectl -n laiive run probe --rm -it --labels app=gateway \
  --image=curlimages/curl --restart=Never -- \
  curl -sS -m 5 -X POST http://retriever:8002/chat   # expect: 403 forbidden

# probes must answer without the key, or the kubelet kills every pod
kubectl -n laiive run probe --rm -it --labels app=gateway \
  --image=curlimages/curl --restart=Never -- curl -sS http://retriever:8002/livez
```
