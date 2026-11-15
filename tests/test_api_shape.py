"""API-shape only: control-plane reads for ECS, Route 53, and RDS.

These three services are not exercised as workloads here. No container
runs, no DNS zone resolves, no database engine starts. The tests assert
only that their control-plane list calls answer successfully with empty
state, which is the part the emulator covers. Anything beyond that needs
real AWS.
"""


def test_ecs_list_clusters_empty(clients):
    response = clients["ecs"].list_clusters()
    assert response["clusterArns"] == []


def test_route53_list_hosted_zones_empty(clients):
    response = clients["route53"].list_hosted_zones()
    assert response["HostedZones"] == []


def test_rds_describe_db_instances_empty(clients):
    response = clients["rds"].describe_db_instances()
    assert response["DBInstances"] == []
