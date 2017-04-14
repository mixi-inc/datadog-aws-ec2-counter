from checks import AgentCheck
from boto3.session import Session

class Instances():
    def __init__(self):
        self.__instances = {}

    def get_availability_zones(self):
        return self.__instances.keys()

    def add_availability_zone(self, name):
        if not self.__instances.get(name):
            self.__instances[name] = {}

    def get_instance_count(self, az, instance_type):
        if self.__instances.get(az) and self.__instances[az].get(instance_type):
            return self.__instances[az][instance_type]

        return 0

    def set_instance_count(self, az, instance_type, count):
        self.add_availability_zone(az)
        self.__instances[az][instance_type] = count
        return self.__instances[az][instance_type]

    def add_instance_count(self, az, instance_type, count):
        self.add_availability_zone(az)

        if not self.__instances[az].get(instance_type):
            self.__instances[az][instance_type] = count
        else:
            self.__instances[az][instance_type] += count

        return self.__instances[az][instance_type]

    def incr_instance_count(self, az, instance_type):
        return self.add_instance_count(az, instance_type, 1)

    def has_instance_type(self, az, instance_type):
        if self.__instances.get(az) and self.__instances[az].get(instance_type):
            return True

        return False

    def get_instance_types(self, az):
        if not self.__instances.get(az):
            return []

        return self.__instances[az].keys()

    def get_instances(self):
        instances = []
        for az in self.get_availability_zones():
            for instance_type in self.get_instance_types(az):
                instance = {
                    'availability_zone' : az,
                    'instance_type'     : instance_type,
                    'count'             : self.get_instance_count(az, instance_type),
                }
                instances.append(instance)

        return instances

class AwsEc2Count(AgentCheck):
    def check(self, instance):
        if not instance.get('region'):
            self.log.error('no region')
            return

        session = Session(region_name = instance['region'])
        ec2 = session.client('ec2')

        running_instances = self.__get_running_instances(ec2)
        self.log.info('running_instances')
        for instance in running_instances.get_instances():
            az, instance_type, count = instance['availability_zone'], instance['instance_type'], instance['count']
            self.log.info('%s : %s = %s' % (az, instance_type, count))
            self.__send_gauge('running.count', az, instance_type, count)

        reserved_instances = self.__get_reserved_instances(ec2)
        self.log.info('reserved_instances')
        for instance in reserved_instances.get_instances():
            az, instance_type, count = instance['availability_zone'], instance['instance_type'], instance['count']
            self.log.info('%s : %s = %s' % (az, instance_type, count))
            self.__send_gauge('reserved.count', az, instance_type, count)

        ondemand_instances = self.__get_ondemand_instances(running_instances, reserved_instances)
        self.log.info('ondemand_instances')
        for instance in ondemand_instances.get_instances():
            az, instance_type, count = instance['availability_zone'], instance['instance_type'], instance['count']
            self.log.info('%s : %s = %s' % (az, instance_type, count))
            if count >= 0:
                self.__send_gauge('ondemand.count', az, instance_type, count)
                if reserved_instances.has_instance_type(az, instance_type):
                    self.__send_gauge('reserved.unused', az, instance_type, 0)
            else:
                self.__send_gauge('ondemand.count', az, instance_type, 0)
                self.__send_gauge('reserved.unused', az, instance_type, abs(count))

    def __send_gauge(self, metric, az, instance_type, count):
        prefix = 'aws_ec2_count.'
        self.gauge(
            prefix + metric,
            count,
            tags = [
                'ac-availability-zone:%s' % az,
                'ac-instance-type:%s'     % instance_type
            ]
        )

    def __get_running_instances(self, ec2):
        instances = Instances()
        next_token = ''
        while True:
            running_instances = ec2.describe_instances(
                Filters = [
                    { 'Name' : 'instance-state-name', 'Values' : [ 'running' ] },
                    { 'Name' : 'tenancy',             'Values' : [ 'default' ] },
                ],
                MaxResults = 100,
                NextToken = next_token,
            )

            for reservation in running_instances['Reservations']:
                for running_instance in reservation['Instances']:
                    # exclude SpotInstance
                    if running_instance.get('SpotInstanceRequestId'):
                        continue
                    # exclude not 'Linux/UNIX' Platform
                    if running_instance.get('Platform'):
                        continue

                    instances.incr_instance_count(
                        running_instance['Placement']['AvailabilityZone'],
                        running_instance['InstanceType'],
                    )

            if running_instances.get('NextToken'):
                next_token = running_instances['NextToken']
            else:
                break

        return instances

    def __get_reserved_instances(self, ec2):
        instances = Instances()

        reserved_instances = ec2.describe_reserved_instances(
            Filters = [
                { 'Name' : 'state',               'Values' : [ 'active' ] },
                { 'Name' : 'scope',               'Values' : [ 'Availability Zone' ] },
                { 'Name' : 'product-description', 'Values' : [ 'Linux/UNIX' ] },
                { 'Name' : 'instance-tenancy',    'Values' : [ 'default' ] },
            ],
        )

        for reserved_instance in reserved_instances['ReservedInstances']:
            # exclude processing status
            modify_requests = ec2.describe_reserved_instances_modifications(
                Filters = [
                    { 'Name' : 'status',                'Values' : [ 'processing' ] },
                    { 'Name' : 'reserved-instances-id', 'Values' : [ reserved_instance['ReservedInstancesId'] ] },
                ],
            )
            if len(modify_requests['ReservedInstancesModifications']) >= 1:
                continue

            instances.add_instance_count(
                reserved_instance['AvailabilityZone'],
                reserved_instance['InstanceType'],
                reserved_instance['InstanceCount'],
            )

        return instances

    def __get_ondemand_instances(self, running_instances, reserved_instances):
        instances = Instances()

        for az in reserved_instances.get_availability_zones():
            for instance_type in reserved_instances.get_instance_types(az):
                instances.set_instance_count(
                    az,
                    instance_type,
                    -1 * reserved_instances.get_instance_count(az, instance_type),
                )

        for az in running_instances.get_availability_zones():
            for instance_type in running_instances.get_instance_types(az):
                instances.add_instance_count(
                    az,
                    instance_type,
                    running_instances.get_instance_count(az, instance_type),
                )

        return instances

