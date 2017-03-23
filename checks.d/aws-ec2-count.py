import boto3
from checks import AgentCheck
from boto3.session import Session

class AwsEc2Count(AgentCheck):
    def check(self, instance):
        if not instance.get('region'):
            self.log.error('no region')
            return

        session = Session(region_name = instance['region'])
        ec2 = session.client('ec2')

        running_instances = self.__get_running_instances(ec2)
        for availability_zone in running_instances.keys():
            for instance_type in running_instances[availability_zone].keys():
                self.__send_gauge(
                    'running.count',
                    running_instances[availability_zone][instance_type],
                    availability_zone, instance_type
                )

        reserved_instances = self.__get_reserved_instances(ec2)
        for availability_zone in reserved_instances.keys():
            for instance_type in reserved_instances[availability_zone].keys():
                self.__send_gauge(
                    'reserved.count',
                    reserved_instances[availability_zone][instance_type],
                    availability_zone, instance_type
                )

        ondemand_instances = self.__get_ondemand_instances(running_instances, reserved_instances)
        for availability_zone in ondemand_instances.keys():
            for instance_type in ondemand_instances[availability_zone].keys():
                if ondemand_instances[availability_zone][instance_type] >= 0:
                    self.__send_gauge(
                        'ondemand.count',
                        ondemand_instances[availability_zone][instance_type],
                        availability_zone, instance_type
                    )
                else:
                    self.__send_gauge(
                        'ondemand.count',
                        0,
                        availability_zone, instance_type
                    )
                    self.__send_gauge(
                        'reserved.unused',
                        abs(ondemand_instances[availability_zone][instance_type]),
                        availability_zone, instance_type
                    )

    def __send_gauge(self, metric, count, availability_zone, instance_type):
        prefix = 'aws_ec2_count.'
        self.gauge(
            prefix + metric,
            count,
            tags=[
                'ac-availability-zone:%s' % availability_zone,
                'ac-instance-type:%s'     % instance_type
            ]
        )

    def __get_running_instances(self, ec2):
        instances = {}
        next_token = ''
        while True:
            running_instances = ec2.describe_instances(
                Filters = [
                    { 'Name' : 'instance-state-name', 'Values' : [ 'running' ] },
                ],
                MaxResults = 100,
                NextToken = next_token,
            )

            for reservation in running_instances['Reservations']:
                for running_instance in reservation['Instances']:
                    # exclude SpotInstance
                    if running_instance.get('SpotInstanceRequestId'):
                        next
                    # exclude 'Windows'
                    if running_instance.get('Platform'):
                        next

                    instance_type     = running_instance['InstanceType']
                    availability_zone = running_instance['Placement']['AvailabilityZone']

                    if not instances.get(availability_zone):
                        instances[availability_zone] = {}

                    if not instances[availability_zone].get(instance_type):
                        instances[availability_zone][instance_type] = 1
                    else:
                        instances[availability_zone][instance_type] += 1

            if running_instances.get('NextToken'):
                next_token = running_instances['NextToken']
            else:
                break

        return instances

    def __get_reserved_instances(self, ec2):
        instances = {}
        next_token = ''

        reserved_instances = ec2.describe_reserved_instances(
            Filters = [
                { 'Name' : 'state', 'Values' : [ 'active' ] },
                { 'Name' : 'scope', 'Values' : [ 'Availability Zone' ] },
            ],
        )

        for reserved_instance in reserved_instances['ReservedInstances']:
            instance_type     = reserved_instance['InstanceType']
            instance_count    = reserved_instance['InstanceCount']
            availability_zone = reserved_instance['AvailabilityZone']

            if not instances.get(availability_zone):
                instances[availability_zone] = {}

            if not instances[availability_zone].get(instance_type):
                instances[availability_zone][instance_type] = instance_count
            else:
                instances[availability_zone][instance_type] += instance_count

        return instances

    def __get_ondemand_instances(self, running_instances, reserved_instances):
        instances = {}

        for availability_zone in running_instances.keys():
            instances[availability_zone] = {}
            for instance_type in running_instances[availability_zone].keys():
                if reserved_instances.get(availability_zone) and reserved_instances[availability_zone].get(instance_type):
                    instances[availability_zone][instance_type] = running_instances[availability_zone][instance_type] - reserved_instances[availability_zone][instance_type]
                else:
                    instances[availability_zone][instance_type] = running_instances[availability_zone][instance_type]

        for availability_zone in reserved_instances.keys():
            if not instances.get(availability_zone):
                instances[availability_zone] = {}
            for instance_type in reserved_instances[availability_zone].keys():
                if (not running_instances.get(availability_zone)) or (not running_instances[availability_zone].get(instance_type)):
                    instances[availability_zone][instance_type] = -1 * reserved_instances[availability_zone][instance_type]

        return instances

