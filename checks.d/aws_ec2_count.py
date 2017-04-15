from checks import AgentCheck
from boto3.session import Session
from collections import OrderedDict

class NormalizationFactor():
    # Normalization Factor
    # - http://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ri-modification-instancemove.html
    __nf = OrderedDict()
    __nf['nano']     =   0.25
    __nf['micro']    =   0.5
    __nf['small']    =   1.0
    __nf['medium']   =   2.0
    __nf['large']    =   4.0
    __nf['xlarge']   =   8.0
    __nf['2xlarge']  =  16.0
    __nf['4xlarge']  =  32.0
    __nf['8xlarge']  =  64.0
    __nf['10xlarge'] =  80.0
    __nf['16xlarge'] = 128.0
    __nf['32xlarge'] = 256.0

    @classmethod
    def get_sorted_all_sizes(cls):
        return cls.__nf.keys()

    @classmethod
    def get_value(cls, size):
        if size not in cls.__nf:
            raise TypeError('unknown instance size : %s' % size)

        return cls.__nf[size]

class InstanceCounter():
    def __init__(self, nf, count=0.0):
        self.__nf    = float(nf)
        self.__count = float(count)

    def get_count(self):
        return self.__count

    def set_count(self, count):
        self.__count = float(count)
        return self.__count

    def add_count(self, count):
        self.__count += float(count)
        return self.__count

    def incr_count(self):
        return self.add_count(1.0)

    def get_footprint(self):
        return self.__count * self.__nf

    def set_footprint(self, footprint):
        self.__count = float(footprint) / self.__nf
        return footprint

class Instances():
    def __init__(self):
        self.__instances = {}

    def has_az(self, az):
        if az in self.__instances:
            return True

        return False

    def add_az(self, az):
        if not self.has_az(az):
            self.__instances[az] = {}

    def get_all_azs(self):
        return sorted(self.__instances.keys())

    def has_family(self, az, family):
        if self.has_az(az) and (family in self.__instances[az]):
            return True

        return False

    def add_family(self, az, family):
        if not self.has_family(az, family):
            self.add_az(az)
            self.__instances[az][family] = {}

    def get_all_families(self, az):
        if not self.has_az(az):
            return []

        return sorted(self.__instances[az].keys())

    def get_all_sizes(self, az, family):
        sizes = []
        for size in NormalizationFactor.get_sorted_all_sizes():
            if self.has(az, family, size):
                sizes.append(size)

        return sizes

    def has(self, az, family, size):
        if self.has_az(az) \
            and self.has_family(az, family) \
            and (size in self.__instances[az][family]):
                return True

        return False

    def get(self, az, family, size):
        if not self.has(az, family, size):
            self.add_family(az, family)
            self.__instances[az][family][size] = InstanceCounter(NormalizationFactor.get_value(size))

        return self.__instances[az][family][size]

    def dump(self):
        instances = []

        for az in self.get_all_azs():
            for family in self.get_all_families(az):
                for size in self.get_all_sizes(az, family):
                    instance = self.get(az, family, size)
                    instances.append({
                        'az'        : az,
                        'itype'     : '%s.%s' % (family, size),
                        'family'    : family,
                        'size'      : size,
                        'count'     : instance.get_count(),
                        'footprint' : instance.get_footprint(),
                    })

        return instances

    # duplicated -----
    def get_instance_count(self, az, itype):
        family, size = itype.split('.', 1)
        if not self.has(az, family, size):
            return 0

        return self.get(az, family, size).get_count()

    def set_instance_count(self, az, itype, count):
        family, size = itype.split('.', 1)
        return self.get(az, family, size).set_count(count)

    def add_instance_count(self, az, itype, count):
        family, size = itype.split('.', 1)
        return self.get(az, family, size).add_count(count)

    def incr_instance_count(self, az, itype):
        return self.add_instance_count(az, itype, 1)

    def has_instance_type(self, az, itype):
        family, size = itype.split('.', 1)
        return self.has(az, family, size)

    def get_instance_types(self, az):
        if not self.has_az(az):
            return []

        instance_types = []
        for family in self.__instances[az].keys():
            for size in self.__instances[az][family].keys():
                instance_types.append('%s.%s' % (family, size))

        return instance_types

    def get_instances(self):
        instances = []
        for az in self.get_all_az():
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

        for az in reserved_instances.get_all_az():
            for instance_type in reserved_instances.get_instance_types(az):
                instances.set_instance_count(
                    az,
                    instance_type,
                    -1 * reserved_instances.get_instance_count(az, instance_type),
                )

        for az in running_instances.get_all_az():
            for instance_type in running_instances.get_instance_types(az):
                instances.add_instance_count(
                    az,
                    instance_type,
                    running_instances.get_instance_count(az, instance_type),
                )

        return instances

