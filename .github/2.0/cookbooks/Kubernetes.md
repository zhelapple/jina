# Cookbook on `Kubernetes` Deployment

Deploy your `Flow` on `Kubernetes`.
## Requirements
- please setup a `Kubernetes` cluster and pull the credentials. e.g.:
  [minikube](https://minikube.sigs.k8s.io/docs/start/) (testing),
  [Google Kubernetes Engine](https://cloud.google.com/kubernetes-engine),
  [Amazon EKS](https://aws.amazon.com/eks),
  [Azure Kubernetes Service](https://azure.microsoft.com/en-us/services/kubernetes-service),
  [Digital Ocean](https://www.digitalocean.com/products/kubernetes/)


## Example
Index Flow:
```python
from jina import Flow
flow = Flow(
    name='test-flow', port_expose=8080, infrastructure='K8S', protocol='http'
).add(
    # name of the service and deployment in Kubernetes
    name='test_executor',
  
```
Search Flow:
```python
from jina import Flow
flow = Flow(
    name='test-flow', port_expose=8080, infrastructure='K8S', protocol='http'
).add(
    # name of the service and deployment in Kubernetes
    name='test_executor',
  
    # There will be 3 deployments and services with 2 replicas each.
    # In addition, there is a head and tail deployed
    # (distribute the request and collect the results)
    #
    #        shard0_replica0, shard0_replica1 
    #      /                                  \
    # head - shard1_replica0, shard1_replica1 - tail
    #      \                                  /
    #        shard2_replica0, shard2_replica1 
    #
    shards=3,
    replicas=2,
  
    # Used Executor has to be containerized
    uses='jinahub+docker://FaissPostgresSearcher',
  
    # Container which runs before the actual Executor to collect the shards
    # This won't be necessary in the close future
    k8s_uses_init='docker://jinaaitmp/postgresdump',
    k8s_init_container_command=["python", "dump.py", "/shared/test_file.txt"],
    
    k8s_mount_path='/shared',
    uses_after='jinahub+docker://MatchMerger',
)
```

## Limitations
- each `Executor` has to be containerized
- only stateless executors are supported when using replicas > 1
- `Kubernetes` is doing `L4` (Network Layer) loadbalancing.
  Since the `Executors` are using long-living `gRPC` connections,
  loadbalancing has to be done on `L7` level (Application Layer).
  We recommend using a proxy based loadbalancing via `envoy`.
  Please inject the `envoy` proxy yourself for now.
  You can use the service mesh `Istio` to automatically inject `envoy` proxies into the `Executor` `Pods` as sidecar.