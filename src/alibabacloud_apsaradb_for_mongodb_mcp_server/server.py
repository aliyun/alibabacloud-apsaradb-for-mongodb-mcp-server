from typing import Dict, Any, Literal, Optional, List
from utils import mcp, logger, get_mongodb_connection_configuration, get_dds_client, get_vpc_client, validate_connection_string, mask_connection_string
from pymongo import MongoClient, errors
from alibabacloud_dds20151201 import models as dds_20151201_models
from alibabacloud_vpc20160428 import models as vpc_20160428_models


"""
Using MQL (MongoDB Query Language) to execute commands on MongoDB
"""


@mcp.tool()
def list_databases(connection_string: str = None) -> str:
    """
    Query the size of all databases in a MongoDB instance.

    :param connection_string: Query connection string by `describe_replica_set_role` if the instance id provided. Prefer the instance's public network address.
    Or use the default value from the environment variables.
    :return:
    """

    if connection_string is None:
        connection_string = get_mongodb_connection_configuration()
    else:
        try:
            validate_connection_string(connection_string)
        except ValueError as e:
            return f"Connection rejected: {str(e)}"
    try:
        client = MongoClient(connection_string, serverSelectionTimeoutMS=5000)
        result = client.admin.command("listDatabases")
        return str(result)
    except Exception as e:
        logger.error(f"Failed to list databases: {str(e)}")
        return f"Failed to list databases, exception: {str(e)}"


@mcp.tool()
def get_top_reusable_space_collections(connection_string, top_n=10):
    """
    Get the top N collections with the most reusable space in a MongoDB instance.

    :param connection_string:  Query connection string by `describe_replica_set_role` if the instance id provided. Prefer the instance's public network address.
    The connection string must include a username and password. The username can be 'root' by default, with the password provided by the caller.
    Or use the default value from the environment variables.
    :param top_n: Number of results to return, default is 10. The type is an integer.
    :return:
    """
    if connection_string is None:
        connection_string = get_mongodb_connection_configuration()
    else:
        try:
            validate_connection_string(connection_string)
        except ValueError as e:
            return f"Connection rejected: {str(e)}"
    try:
        client = MongoClient(connection_string, serverSelectionTimeoutMS=5000)
    except errors.ConnectionFailure as e:
        logger.error(f"Failed to connect to MongoDB: {e}, connection_string: {mask_connection_string(connection_string)}")
        return f"Failed to connect to MongoDB: {e}"

    results = []
    for db_name in client.list_database_names():
        db = client[db_name]
        for coll_name in db.list_collection_names():
            try:
                stats = db.command("collStats", coll_name)
                reusable_space = stats["wiredTiger"]["block-manager"]["file bytes available for reuse"]
                results.append({"database": db_name, "collection": coll_name, "reusable_bytes": reusable_space})
            except errors.OperationFailure as e:
                logger.warning(f"Failed to fetch stats for {db_name}.{coll_name}: {e}")
            except KeyError as e:
                logger.warning(f"Missing expected reuse field in stats for {db_name}.{coll_name}: {e}")

    results.sort(key=lambda x: x["reusable_bytes"], reverse=True)
    return results[:top_n]


"""
Using ApsaraDB OpenAPI for instance operations
"""


@mcp.tool()
def describe_available_zones(region_id: str):
    """
    Query available zones for MongoDB instances.

    :param region_id: Queries available zones in the specified region (e.g., cn-hangzhou).
    """

    client = get_dds_client()
    describe_available_zones_request = dds_20151201_models.DescribeAvailabilityZonesRequest(
        region_id=region_id
    )
    try:
        response = client.describe_availability_zones(describe_available_zones_request)
        return response.body.to_map()
    except Exception as e:
        logger.error(f"Failed to describe available zones: {str(e)}")
        return f"Failed to describe available zones, exception: {str(e)}"


@mcp.tool()
def describe_available_resource(
        region_id: str,
        zone_id: str,
        instance_charge_type: str,
        db_type: str,
        storage_type: str,
        engine_version: str,
        replication_factor: str
):
    """
    Query available resource(instance class) for MongoDB instances.

    :param region_id: The region ID of the MongoDB instance.
    :param zone_id: The zone ID of the MongoDB instance. Query available zones by `describe_available_zones`.
    :param instance_charge_type: Instance payment type. Values: `PrePaid`, `PostPaid`.
    :param db_type: Instance category. Values: `normal`, `sharding`. `normal` means replication set, `sharding` means cluster.
    :param storage_type: Storage Type. Values: `local_ssd`, `cloud_essd1`, `cloud_essd2`, `cloud_essd3`, `cloud_auto`.
        For versions less than 4.2, only `local_ssd` is available; for versions greater than 4.2, there are 3 `cloud_xxx` options;
        version 4.2 includes all four.
    :param engine_version: The version of the MongoDB instance. Values: 3.4, 4.0, 4.2, 4.4, 5.0, 6.0, 7.0, 8.0.
    :param replication_factor: The node number of the MongoDB instance. Values: 1, 3, 5, 7.
    """

    client = get_dds_client()
    describe_available_resource_request = dds_20151201_models.DescribeAvailableResourceRequest(
        region_id=region_id,
        zone_id=zone_id,
        instance_charge_type=instance_charge_type,
        db_type=db_type,
        storage_type=storage_type,
        engine_version=engine_version,
        replication_factor=replication_factor
    )
    try:
        response = client.describe_available_resource(describe_available_resource_request)
        return response.body.to_map()
    except Exception as e:
        logger.error(f"Failed to describe available resource: {str(e)}")
        return f"Failed to describe available resource, exception: {str(e)}"


@mcp.tool()
def describe_vpcs(
        region_id: str,
        vpc_id: str = None,
        vpc_name: str = None,
        page_number: int = 1,
        page_size: int = 10,
):
    """
    Query VPC list.

    :param region_id: The region ID of the VPC.
    :param vpc_id: The ID of the VPC. Up to 20 VPC IDs can be specified, separated by commas.
    :param vpc_name: The name of the VPC.
    :param page_number: The page number of the list. Default: 1.
    :param page_size: The number of entries per page. Maximum value: 50. Default: 10.
    """

    client = get_vpc_client(region_id)
    describe_vpcs_request = vpc_20160428_models.DescribeVpcsRequest(
        region_id=region_id,
        page_number=page_number,
        page_size=page_size
    )
    if vpc_id:
        describe_vpcs_request.vpc_id = vpc_id
    if vpc_name:
        describe_vpcs_request.vpc_name = vpc_name

    try:
        response = client.describe_vpcs(describe_vpcs_request)
        return response.body.to_map()
    except Exception as e:
        logger.error(f"Failed to describe vpcs in region {region_id}: {str(e)}")
        return f"Failed to describe vpcs in region {region_id}, exception: {str(e)}"


@mcp.tool()
def describe_vswitches(
        region_id: str,
        vpc_id: str = None,
        vswitch_id: str = None,
        vswitch_name: str = None,
        zone_id: str = None,
        page_number: int = 1,
        page_size: int = 10,
):
    """
    Query VSwitch list.

    :param region_id: The region ID of the VSwitch.
    :param vpc_id: The ID of the VPC to which the VSwitch belongs.
    :param vswitch_id: The ID of the specified zone VSwitch to query.
    :param vswitch_name: The name of the VSwitch.
    :param zone_id: The zone ID of the VSwitch.
    :param page_number: The page number of the list. Default: 1.
    :param page_size: The number of entries per page. Maximum value: 50. Default: 10.
    """

    client = get_vpc_client(region_id)
    describe_vswitches_request = vpc_20160428_models.DescribeVSwitchesRequest(
        region_id=region_id,
        page_number=page_number,
        page_size=page_size
    )
    if vpc_id:
        describe_vswitches_request.vpc_id = vpc_id
    if vswitch_id:
        describe_vswitches_request.vswitch_id = vswitch_id
    if vswitch_name:
        describe_vswitches_request.vswitch_name = vswitch_name
    if zone_id:
        describe_vswitches_request.zone_id = zone_id

    try:
        response = client.describe_vswitches(describe_vswitches_request)
        return response.body.to_map()
    except Exception as e:
        logger.error(f"Failed to describe vswitches: {str(e)}")
        return f"Failed to describe vswitches, exception: {str(e)}"


@mcp.tool()
def describe_db_instances(region_id: str):
    """
    Queries all MongoDB instances in a region.

    :param region_id: queries instances in region id (e.g., cn-hangzhou)
    """

    client = get_dds_client()
    describe_db_instances_request = dds_20151201_models.DescribeDBInstancesRequest(
        region_id=region_id
    )
    try:
        response = client.describe_dbinstances(describe_db_instances_request)
        return response.body.to_map()
    except Exception as e:
        logger.error(f"Failed to describe db instances: {str(e)}")
        return f"Failed to describe db instances, exception: {str(e)}"


@mcp.tool()
def describe_db_instance_attribute(db_instance_id: str):
    """
    Query detailed information about a specific MongoDB instance.

    :param db_instance_id: The ID of the MongoDB instance.
    :return:
    """

    client = get_dds_client()
    describe_db_instance_attribute_request = dds_20151201_models.DescribeDBInstanceAttributeRequest(
        dbinstance_id=db_instance_id
    )
    try:
        response = client.describe_dbinstance_attribute(describe_db_instance_attribute_request)
        return response.body.to_map()
    except Exception as e:
        logger.error(f"Failed to describe db instance attribute: {str(e)}")
        return f"Failed to describe db instance attribute, exception: {str(e)}"


@mcp.tool()
def describe_replica_set_role(db_instance_id: str):
    """
    Query connection string and role information of a MongoDB instance.
    Note that public network access information can only be retrieved through this function.

    :param db_instance_id: The ID of the MongoDB instance.
    :return:
    """

    client = get_dds_client()
    describe_replica_set_role_request = dds_20151201_models.DescribeReplicaSetRoleRequest(
        dbinstance_id=db_instance_id
    )
    try:
        response = client.describe_replica_set_role(describe_replica_set_role_request)
        return response.body.to_map()
    except Exception as e:
        logger.error(f"Failed to describe replicaset role: {str(e)}")
        return f"Failed to describe replicaset role, exception: {str(e)}"


@mcp.tool()
def allocate_public_network_address(db_instance_id: str):
    """
    Assign a public IP address to all non-hidden nodes within instance to enable public network access.

    :param db_instance_id: The ID of the MongoDB instance.
    :return:
    """

    client = get_dds_client()
    allocate_public_network_address_request = dds_20151201_models.AllocatePublicNetworkAddressRequest(
        dbinstance_id=db_instance_id
    )
    try:
        response = client.allocate_public_network_address(allocate_public_network_address_request)
        return response.body.to_map()
    except Exception as e:
        logger.error(f"Failed to allocate public network address: {str(e)}")
        return f"Failed to allocate public network address, exception: {str(e)}"


@mcp.tool()
def create_db_instance(
        region_id: str,
        zone_id: str,
        engine_version: str,
        db_instance_class: str,
        db_instance_storage: int,
        account_password: str,
        charge_type: str,
        vpc_id: str,
        vswitch_id: str,
        storage_type: str,
        security_ip_list: str = None,
        period: int = None,
        replication_factor: int = 3
):
    """
    Create an MongoDB instance.

    :param region_id: Region ID.
    :param zone_id: Zone ID.
    :param engine_version: Database version.
    :param db_instance_class: Instance specification. Query valid instance class by `describe_available_resource` tool in advance.
        Instance classes ending with .c are general purpose, while those ending with .d are dedicated.
        General purpose instances typically have faster creation speeds compared to dedicated instances.
    :param db_instance_storage: Storage space in GB.
    :param account_password: Password of root user.
    :param charge_type: Instance payment type. Values: PrePaid, PostPaid.
    :param vpc_id: VPC ID. Query available vpc by `describe_vpcs`.
    :param vswitch_id: VSwitch ID in specified zone. Query available switch by `describe_vswitches`.
    :param storage_type: Storage Type. Values: local_ssd, cloud_essd1, cloud_essd2, cloud_essd3, cloud_auto.
        For versions less than 4.2, only local_ssd is available; for versions greater than 4.2, there are 3 cloud_xxx options;
        version 4.2 includes all four.
    :param security_ip_list: IP whitelist, separated by commas. Default: "127.0.0.1".
    :param period: The purchase duration for the instance, measured in months. This parameter must be provided when the
        charge_type parameter is set to PrePaid.
    :param replication_factor: The node number of the MongoDB instance. Values: 1, 3, 5, 7.
    """

    if charge_type == "PrePaid" and not period:
        raise "period is required when charge_type is PrePaid"

    client = get_dds_client()
    create_db_instance_request = dds_20151201_models.CreateDBInstanceRequest(
        region_id=region_id,
        zone_id=zone_id,
        engine_version=engine_version,
        dbinstance_class=db_instance_class,
        dbinstance_storage=db_instance_storage,
        account_password=account_password,
        charge_type=charge_type,
        vpc_id=vpc_id,
        v_switch_id=vswitch_id,
        storage_type=storage_type,
    )
    if security_ip_list:
        create_db_instance_request.security_iplist = security_ip_list
    if period:
        create_db_instance_request.period = period
    if replication_factor:
        create_db_instance_request.replication_factor = replication_factor

    try:
        response = client.create_dbinstance(create_db_instance_request)
        return response.body.to_map()
    except Exception as e:
        logger.error(f"Failed to create db instance: {str(e)}")
        return f"Failed to create db instance, exception: {str(e)}"


def main(transport: Literal["stdio", "sse"] = "stdio"):
    """Main entry point to run the MCP server."""
    logger.info(f"Starting ApsaraDB MongoDB MCP server with {transport} mode...")
    mcp.run(transport=transport)


if __name__ == "__main__":
    main()
