# -*- coding: utf-8 -*-
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
        azs = [ az ]
        if az is None:
            azs = self.get_all_azs()

        sizes = []
        for size in NormalizationFactor.get_sorted_all_sizes():
            for az in azs:
                if self.has(az, family, size):
                    sizes.append(size)
                    break

        return sizes

    def has(self, az, family, size):
        if self.has_az(az) \
            and self.has_family(az, family) \
            and (size in self.__instances[az][family]):
                return True

        return False

    def has_itype(self, az, itype):
        family, size = itype.split('.', 1)
        return self.has(az, family, size)

    def get(self, az, family, size):
        if not self.has(az, family, size):
            self.add_family(az, family)
            self.__instances[az][family][size] = InstanceCounter(NormalizationFactor.get_value(size))

        return self.__instances[az][family][size]

    def get_itype(self, az, itype):
        family, size = itype.split('.', 1)
        return self.get(az, family, size)

    def get_all_instances(self, az=None):
        azs = None
        if az is None:
            azs = self.get_all_azs()
        else:
            azs = [ az ]

        instances = []
        for az in azs:
            for family in self.get_all_families(az):
                for size in self.get_all_sizes(az, family):
                    instances.append({
                        'az'      : az,
                        'family'  : family,
                        'size'    : size,
                        'counter' : self.get(az, family, size),
                    })
        return instances

    def dump(self):
        instances = []
        for instance in self.get_all_instances():
            instances.append({
                'az'        : instance['az'],
                'itype'     : '%s.%s' % (instance['family'], instance['size']),
                'family'    : instance['family'],
                'size'      : instance['size'],
                'count'     : instance['counter'].get_count(),
                'footprint' : instance['counter'].get_footprint(),
            })
        return instances


class InstanceFetcher():
    def __init__(self, region):
        session = Session(region_name=region)
        self.__ec2 = session.client('ec2')

    def get_running_instances(self):
        instances = Instances()
        next_token = ''
        while True:
            running_instances = self.__ec2.describe_instances(
                Filters=[
                    { 'Name' : 'instance-state-name', 'Values' : [ 'running' ] },
                    { 'Name' : 'tenancy',             'Values' : [ 'default' ] },
                ],
                MaxResults=100,
                NextToken=next_token,
            )

            for reservation in running_instances['Reservations']:
                for running_instance in reservation['Instances']:
                    # exclude SpotInstance
                    if 'SpotInstanceRequestId' in running_instance:
                        continue
                    # exclude not 'Linux/UNIX' Platform
                    if 'Platform' in running_instance:
                        continue

                    instances.get_itype(
                        running_instance['Placement']['AvailabilityZone'],
                        running_instance['InstanceType'],
                    ).incr_count()

            if 'NextToken' in running_instances:
                next_token = running_instances['NextToken']
            else:
                break

        return instances

    def get_reserved_instances(self):
        instances = Instances()

        reserved_instances = self.__ec2.describe_reserved_instances(
            Filters=[
                { 'Name' : 'state',               'Values' : [ 'active' ] },
                { 'Name' : 'product-description', 'Values' : [ 'Linux/UNIX' ] },
                { 'Name' : 'instance-tenancy',    'Values' : [ 'default' ] },
            ],
        )

        for reserved_instance in reserved_instances['ReservedInstances']:
            # exclude processing status
            modify_requests = self.__ec2.describe_reserved_instances_modifications(
                Filters=[
                    { 'Name' : 'status',                'Values' : [ 'processing' ] },
                    { 'Name' : 'reserved-instances-id', 'Values' : [ reserved_instance['ReservedInstancesId'] ] },
                ],
            )
            if len(modify_requests['ReservedInstancesModifications']) >= 1:
                for modification in modify_requests['ReservedInstancesModifications']:
                    for result in modification['ModificationResults']:
                        if 'ReservedInstancesId' not in result:
                            # MEMO: RI 契約が変更中( status = processing ) かつ、
                            #       変更先の RI 契約が確定していない場合、
                            #       RI の集計にずれが発生するタイミングがあるので、RI の集計はしない
                            return None

                # MEMO: RI 契約が変更中かつ、変更先の RI 契約が確定している場合
                #       変更元の RI を集計すると2重計上になるので集計から外す
                continue

            az = None
            if reserved_instance['Scope'] == 'Region':
                az = 'region'
            else:
                az = reserved_instance['AvailabilityZone']

            instances.get_itype(
                az,
                reserved_instance['InstanceType'],
            ).add_count(reserved_instance['InstanceCount'])

        return instances

    def get_ondemand_instances(self, running_instances, reserved_instances):
        ondemand_instances = Instances()
        unused_instances   = Instances()

        for reserved in reserved_instances.get_all_instances(az='region'):
            unused_instances.get(
                'region', reserved['family'], reserved['size']
            ).set_count(reserved['counter'].get_count())

        for running in running_instances.get_all_instances():
            az, family, size = running['az'], running['family'], running['size']
            count = running['counter'].get_count()

            if reserved_instances.has(az, family, size):
                unused_counter = unused_instances.get(az, family, size)
                count -= reserved_instances.get(az, family, size).get_count()
                if count <= 0.0:
                    unused_counter.set_count(abs(count))
                    count = 0.0
                else:
                    unused_counter.set_count(0)

            if unused_instances.has('region', family, size):
                unused_counter = unused_instances.get('region', family, size)
                count -= unused_counter.get_count()
                if count <= 0.0:
                    unused_counter.set_count(abs(count))
                    count = 0.0
                else:
                    unused_counter.set_count(0)

            ondemand_instances.get(az, family, size).set_count(count)

        for unused in unused_instances.get_all_instances(az='region'):
            family, size = unused['family'], unused['size']
            if unused['counter'].get_footprint() == 0.0:
                continue
            for size in ondemand_instances.get_all_sizes(None, family):
                for az in ondemand_instances.get_all_azs():
                    if not ondemand_instances.has(az, family, size):
                        continue

                    ondemand = ondemand_instances.get(az, family, size)
                    if ondemand.get_footprint() >= unused['counter'].get_footprint():
                        ondemand.set_footprint(ondemand.get_footprint() - unused['counter'].get_footprint())
                        unused['counter'].set_footprint(0.0)
                        break
                    else:
                        unused['counter'].set_footprint(unused['counter'].get_footprint() - ondemand.get_footprint())
                        ondemand.set_footprint(0.0)

        return ondemand_instances, unused_instances


class AwsEc2Count(AgentCheck):
    def check(self, instance):
        if not 'region' in instance:
            self.log.error('no region')
            return

        fetcher = InstanceFetcher(instance['region'])

        reserved_instances = fetcher.get_reserved_instances()
        if reserved_instances is None:
            return
        self.__send_instance_info('reserved', reserved_instances)

        running_instances = fetcher.get_running_instances()
        self.__send_instance_info('running', running_instances)

        ondemand_instances, unused_instances = fetcher.get_ondemand_instances(running_instances, reserved_instances)
        self.__send_instance_info('ondemand', ondemand_instances)
        self.__send_instance_info('reserved_unused', unused_instances)

    def __send_instance_info(self, category, instances):
        self.log.info(category)
        for instance in instances.dump():
            self.log.info('%s : %s = %s (%s)' % (instance['az'], instance['itype'], instance['count'], instance['footprint']))
            self.__send_count(category, instance)

    def __send_count(self, category, instance):
        self.__send_gauge(
            '%s.count' % category,
            instance['count'],
            [
                'ac-az:%s'     % instance['az'],
                'ac-type:%s'   % instance['itype'],
                'ac-family:%s' % instance['family'],
            ]
        )
        self.__send_gauge(
            '%s.footprint' % category,
            instance['footprint'],
            [
                'ac-az:%s'     % instance['az'],
                'ac-type:%s'   % instance['itype'],
                'ac-family:%s' % instance['family'],
            ]
        )

    def __send_gauge(self, metric, value, tags):
        prefix = 'aws_ec2_count_1.'
        self.gauge(
            prefix + metric,
            value,
            tags=tags
        )

