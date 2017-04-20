import unittest
from mock import Mock
from mock import patch

import aws_ec2_count

class TestNormalizationFactor(unittest.TestCase):
    def test_get_sorted_add_sizes(self):
        self.assertEqual(
            aws_ec2_count.NormalizationFactor.get_sorted_all_sizes(),
            [
                'nano',
                'micro',
                'small',
                'medium',
                'large',
                'xlarge',
                '2xlarge',
                '4xlarge',
                '8xlarge',
                '10xlarge',
                '16xlarge',
                '32xlarge',
            ]
        )

    def test_get_value(self):
        self.assertEqual(aws_ec2_count.NormalizationFactor.get_value('medium'), 2.0)
        self.assertEqual(aws_ec2_count.NormalizationFactor.get_value('10xlarge'), 80.0)
        self.assertRaises(TypeError, aws_ec2_count.NormalizationFactor.get_value, ('invalid'))

class TestInstanceCounter(unittest.TestCase):
    def test_basic(self):
        counter = aws_ec2_count.InstanceCounter(0.5, 1)
        self.assertEqual(counter.get_count(), 1.0)
        self.assertEqual(counter.set_count(2), 2.0)
        self.assertEqual(counter.get_count(), 2.0)
        self.assertEqual(counter.add_count(3), 5.0)
        self.assertEqual(counter.get_count(), 5.0)
        self.assertEqual(counter.incr_count(), 6.0)
        self.assertEqual(counter.get_count(), 6.0)
        self.assertEqual(counter.get_footprint(), 3.0)
        self.assertEqual(counter.set_footprint(10), 10.0)
        self.assertEqual(counter.get_footprint(), 10.0)
        self.assertEqual(counter.get_count(), 20.0)

        counter = aws_ec2_count.InstanceCounter(0.5)
        self.assertEqual(counter.get_count(), 0.0)

class TestInstances(unittest.TestCase):
    def test_az(self):
        instances = aws_ec2_count.Instances()

        self.assertFalse(instances.has_az('region-1a'))
        self.assertEqual(instances.get_all_azs(), [])

        instances.add_az('region-1a')
        self.assertTrue(instances.has_az('region-1a'))
        self.assertEqual(instances.get_all_azs(), ['region-1a'])

        instances.add_az('region-1a')
        self.assertEqual(instances.get_all_azs(), ['region-1a'])

        instances.add_az('region-1b')
        instances.add_az('region-1d')
        instances.add_az('region-1c')
        self.assertEqual(instances.get_all_azs(), ['region-1a', 'region-1b', 'region-1c', 'region-1d'])

    def test_family(self):
        instances = aws_ec2_count.Instances()

        self.assertFalse(instances.has_family('region-1a', 'c3'))
        self.assertEqual(instances.get_all_families('region-1a'), [])

        instances.add_family('region-1a', 'c3')
        self.assertTrue(instances.has_family('region-1a', 'c3'))
        self.assertEqual(instances.get_all_families('region-1a'), ['c3'])

        instances.add_family('region-1a', 'c4')
        instances.add_family('region-1b', 'c5')
        self.assertEqual(instances.get_all_families('region-1a'), ['c3', 'c4'])

    def test_instance(self):
        instances = aws_ec2_count.Instances()

        self.assertFalse(instances.has('region-1a', 'c3', 'large'))

        self.assertTrue(isinstance(instances.get('region-1a', 'c3', 'large'), aws_ec2_count.InstanceCounter))
        self.assertTrue(instances.has('region-1a', 'c3', 'large'))
        self.assertTrue(instances.get('region-1a', 'c3', 'large') is not None)

        instances.get('region-1a', 'c3', '4xlarge')
        instances.get('region-1a', 'c3', '2xlarge')
        instances.get('region-1a', 'c3', 'xlarge')
        instances.get('region-1b', 'c3', '8xlarge')
        instances.get('region-1b', 'c3', '4xlarge')
        instances.get('region-1b', 'c3', 'large')
        parts = instances.get_all_sizes('region-1a', 'c3')
        self.assertEqual(parts, ['large', 'xlarge', '2xlarge', '4xlarge'])
        parts = instances.get_all_sizes('region-1b', 'c3')
        self.assertEqual(parts, ['large', '4xlarge', '8xlarge'])
        parts = instances.get_all_sizes(None, 'c3')
        self.assertEqual(parts, ['large', 'xlarge', '2xlarge', '4xlarge', '8xlarge'])


    def test_get_all_instances(self):
        instances = aws_ec2_count.Instances()
        instances.get('region-1a', 'm3', 'medium').set_count(5)
        instances.get('region-1a', 'm3', 'large').set_count(5)
        instances.get('region-1a', 'm4', 'large').set_count(5)
        instances.get('region-1b', 'c3', 'large').set_count(5)
        instances.get('region-1b', 'c3', 'xlarge').set_count(5)
        instances.get('region-1b', 't2', 'micro').set_count(5)

        patterns= [
            { 'az': 'region-1a', 'family': 'm3', 'size': 'medium', 'count': 5.0, 'footprint': 10.0 },
            { 'az': 'region-1a', 'family': 'm3', 'size': 'large',  'count': 5.0, 'footprint': 20.0 },
            { 'az': 'region-1a', 'family': 'm4', 'size': 'large',  'count': 5.0, 'footprint': 20.0 },
            { 'az': 'region-1b', 'family': 'c3', 'size': 'large',  'count': 5.0, 'footprint': 20.0 },
            { 'az': 'region-1b', 'family': 'c3', 'size': 'xlarge', 'count': 5.0, 'footprint': 40.0 },
            { 'az': 'region-1b', 'family': 't2', 'size': 'micro',  'count': 5.0, 'footprint':  2.5 },
        ]
        for instance in instances.get_all_instances():
            pattern = patterns.pop(0)
            for key in instance.keys():
                if key == 'az' or key == 'family' or key == 'size':
                    self.assertEqual(instance[key], pattern[key])
                else:
                    self.assertEqual(key, 'counter')
                    self.assertTrue(isinstance(instance[key], aws_ec2_count.InstanceCounter))
                    self.assertEqual(instance[key].get_count(), pattern['count'])
                    self.assertEqual(instance[key].get_footprint(), pattern['footprint'])

        patterns= [
            { 'az': 'region-1a', 'family': 'm3', 'size': 'medium', 'count': 5.0, 'footprint': 10.0 },
            { 'az': 'region-1a', 'family': 'm3', 'size': 'large',  'count': 5.0, 'footprint': 20.0 },
            { 'az': 'region-1a', 'family': 'm4', 'size': 'large',  'count': 5.0, 'footprint': 20.0 },
        ]
        for instance in instances.get_all_instances(az='region-1a'):
            pattern = patterns.pop(0)
            for key in instance.keys():
                if key == 'az' or key == 'family' or key == 'size':
                    self.assertEqual(instance[key], pattern[key])
                else:
                    self.assertEqual(key, 'counter')
                    self.assertTrue(isinstance(instance[key], aws_ec2_count.InstanceCounter))
                    self.assertEqual(instance[key].get_count(), pattern['count'])
                    self.assertEqual(instance[key].get_footprint(), pattern['footprint'])

    def test_dump(self):
        instances = aws_ec2_count.Instances()
        instances.get('region-1a', 'm3', 'medium').set_count(5)
        instances.get('region-1a', 'm3', 'large').set_count(5)
        instances.get('region-1a', 'm4', 'large').set_count(5)
        instances.get('region-1b', 'c3', 'large').set_count(5)
        instances.get('region-1b', 'c3', 'xlarge').set_count(5)
        instances.get('region-1b', 't2', 'micro').set_count(5)

        self.assertEqual(instances.dump(), [
            { 'az': 'region-1a', 'itype': 'm3.medium', 'family': 'm3', 'size': 'medium', 'count': 5.0, 'footprint': 10.0 },
            { 'az': 'region-1a', 'itype': 'm3.large',  'family': 'm3', 'size': 'large',  'count': 5.0, 'footprint': 20.0 },
            { 'az': 'region-1a', 'itype': 'm4.large',  'family': 'm4', 'size': 'large',  'count': 5.0, 'footprint': 20.0 },
            { 'az': 'region-1b', 'itype': 'c3.large',  'family': 'c3', 'size': 'large',  'count': 5.0, 'footprint': 20.0 },
            { 'az': 'region-1b', 'itype': 'c3.xlarge', 'family': 'c3', 'size': 'xlarge', 'count': 5.0, 'footprint': 40.0 },
            { 'az': 'region-1b', 'itype': 't2.micro',  'family': 't2', 'size': 'micro',  'count': 5.0, 'footprint':  2.5 },
        ])

class TestInstanceFetcher(unittest.TestCase):
    def setUp(self):
        self.mock_ec2_client = Mock()

        self.mock_session_object = Mock()
        self.mock_session_object.client.return_value = self.mock_ec2_client

        self.patcher_session = patch('aws_ec2_count.Session')
        self.mock_session = self.patcher_session.start()
        self.mock_session.return_value = self.mock_session_object

    def tearDown(self):
        self.patcher_session.stop()

    def test_get_running_instances(self):
        self.mock_ec2_client.describe_instances.return_value = {
            'Reservations': [
                {
                    'Instances': [
                        {
                            # SpotInstance
                            'Placement' : { 'AvailabilityZone' : 'region-1a' },
                            'InstanceType' : 'c3.large',
                            'SpotInstanceRequestId': 'hoge',
                        },
                        {
                            # not 'Linux/UNIX' Platform
                            'Placement' : { 'AvailabilityZone' : 'region-1a' },
                            'InstanceType' : 'c3.large',
                            'Platform': 'hoge',
                        },
                        {
                            'Placement' : { 'AvailabilityZone' : 'region-1a' },
                            'InstanceType' : 'c3.large',
                        },
                        {
                            'Placement' : { 'AvailabilityZone' : 'region-1a' },
                            'InstanceType' : 'c3.large',
                        },
                    ]
                },
                {
                    'Instances': [
                        {
                            'Placement' : { 'AvailabilityZone' : 'region-1a' },
                            'InstanceType' : 'c3.xlarge',
                        },
                        {
                            'Placement' : { 'AvailabilityZone' : 'region-1b' },
                            'InstanceType' : 'c3.xlarge',
                        },
                    ]
                },
            ]
        }

        fetcher = aws_ec2_count.InstanceFetcher('region')
        instances = fetcher.get_running_instances()
        self.assertEqual(instances.dump(), [
            { 'az': 'region-1a', 'itype': 'c3.large',  'family': 'c3', 'size': 'large',  'count': 2.0, 'footprint': 8.0 },
            { 'az': 'region-1a', 'itype': 'c3.xlarge', 'family': 'c3', 'size': 'xlarge', 'count': 1.0, 'footprint': 8.0 },
            { 'az': 'region-1b', 'itype': 'c3.xlarge', 'family': 'c3', 'size': 'xlarge', 'count': 1.0, 'footprint': 8.0 },
        ])

    def test_get_reserved_instances(self):
        self.mock_ec2_client.describe_reserved_instances.return_value = {
            'ReservedInstances' : [
                {
                    'ReservedInstancesId': 1,
                    'AvailabilityZone'   : 'region-1a',
                    'InstanceType'       : 'c3.large',
                    'InstanceCount'      : 2,
                },
                {
                    'ReservedInstancesId': 2,
                    'AvailabilityZone'   : 'region-1a',
                    'InstanceType'       : 'c3.large',
                    'InstanceCount'      : 1,
                },
                {
                    'ReservedInstancesId': 3,
                    'AvailabilityZone'   : 'region-1a',
                    'InstanceType'       : 'c3.xlarge',
                    'InstanceCount'      : 4,
                },
                {
                    'ReservedInstancesId': 4,
                    'AvailabilityZone'   : 'region-1b',
                    'InstanceType'       : 'c3.large',
                    'InstanceCount'      : 4,
                },
                {
                    # processing status
                    'ReservedInstancesId': 5,
                    'AvailabilityZone'   : 'region-1b',
                    'InstanceType'       : 'c3.xlarge',
                    'InstanceCount'      : 5,
                },
            ],
        }
        self.mock_ec2_client.describe_reserved_instances_modifications.side_effect = [
            { 'ReservedInstancesModifications': [] },
            { 'ReservedInstancesModifications': [] },
            { 'ReservedInstancesModifications': [] },
            { 'ReservedInstancesModifications': [] },
            { 'ReservedInstancesModifications': [ {} ] }, # processing status
        ]

        fetcher = aws_ec2_count.InstanceFetcher('region')
        instances = fetcher.get_reserved_instances()
        self.assertEqual(instances.dump(), [
            { 'az': 'region-1a', 'itype': 'c3.large',  'family': 'c3', 'size': 'large',  'count': 3.0, 'footprint': 12.0 },
            { 'az': 'region-1a', 'itype': 'c3.xlarge', 'family': 'c3', 'size': 'xlarge', 'count': 4.0, 'footprint': 32.0 },
            { 'az': 'region-1b', 'itype': 'c3.large',  'family': 'c3', 'size': 'large',  'count': 4.0, 'footprint': 16.0 },
        ])

    def test_get_ondemand_instances(self):
        fetcher = aws_ec2_count.InstanceFetcher('region')

        # az
        running_instances  = aws_ec2_count.Instances()
        running_instances.get('region-1a', 'c4', 'large').set_count(5)
        running_instances.get('region-1b', 'c4', 'large').set_count(10)
        running_instances.get('region-1b', 'c4', 'xlarge').set_count(10)
        reserved_instances = aws_ec2_count.Instances()
        reserved_instances.get('region-1a', 'c4', 'large').set_count(10)
        reserved_instances.get('region-1b', 'c4', 'large').set_count(5)
        ondemand_instances, unused_instances = fetcher.get_ondemand_instances(running_instances, reserved_instances)
        self.assertEqual(ondemand_instances.dump(), [
            { 'az': 'region-1a', 'itype': 'c4.large',  'family': 'c4', 'size': 'large',  'count':  0.0, 'footprint':  0.0 },
            { 'az': 'region-1b', 'itype': 'c4.large',  'family': 'c4', 'size': 'large',  'count':  5.0, 'footprint': 20.0 },
            { 'az': 'region-1b', 'itype': 'c4.xlarge', 'family': 'c4', 'size': 'xlarge', 'count': 10.0, 'footprint': 80.0 },
        ])
        self.assertEqual(unused_instances.dump(), [
            { 'az': 'region-1a', 'itype': 'c4.large', 'family': 'c4', 'size': 'large', 'count': 5.0, 'footprint': 20.0 },
            { 'az': 'region-1b', 'itype': 'c4.large', 'family': 'c4', 'size': 'large', 'count': 0.0, 'footprint':  0.0 },
        ])

        # region
        running_instances  = aws_ec2_count.Instances()
        running_instances.get('region-1a', 'c4', 'small').set_count(1)
        running_instances.get('region-1a', 'c4', 'medium').set_count(1)
        running_instances.get('region-1a', 'c4', 'large').set_count(1)
        running_instances.get('region-1b', 'c4', 'large').set_count(1)
        reserved_instances = aws_ec2_count.Instances()
        reserved_instances.get('region', 'c4', 'large').set_count(3)
        ondemand_instances, unused_instances = fetcher.get_ondemand_instances(running_instances, reserved_instances)
        self.assertEqual(ondemand_instances.dump(), [
            { 'az': 'region-1a', 'itype': 'c4.small',  'family': 'c4', 'size': 'small',  'count': 0.0, 'footprint': 0.0 },
            { 'az': 'region-1a', 'itype': 'c4.medium', 'family': 'c4', 'size': 'medium', 'count': 0.0, 'footprint': 0.0 },
            { 'az': 'region-1a', 'itype': 'c4.large',  'family': 'c4', 'size': 'large',  'count': 0.0, 'footprint': 0.0 },
            { 'az': 'region-1b', 'itype': 'c4.large',  'family': 'c4', 'size': 'large',  'count': 0.0, 'footprint': 0.0 },
        ])
        self.assertEqual(unused_instances.dump(), [
            { 'az': 'region', 'itype': 'c4.large', 'family': 'c4', 'size': 'large', 'count': 0.25, 'footprint': 1.0 },
        ])

        running_instances  = aws_ec2_count.Instances()
        running_instances.get('region-1a', 'c4', 'small').set_count(1)
        running_instances.get('region-1a', 'c4', 'medium').set_count(1)
        running_instances.get('region-1a', 'c4', 'large').set_count(1)
        running_instances.get('region-1b', 'c4', 'small').set_count(2)
        running_instances.get('region-1b', 'c4', 'medium').set_count(1)
        running_instances.get('region-1b', 'c4', 'large').set_count(1)
        reserved_instances = aws_ec2_count.Instances()
        reserved_instances.get('region', 'c4', 'large').set_count(3)
        ondemand_instances, unused_instances = fetcher.get_ondemand_instances(running_instances, reserved_instances)
        self.assertEqual(ondemand_instances.dump(), [
            { 'az': 'region-1a', 'itype': 'c4.small',  'family': 'c4', 'size': 'small',  'count': 0.0, 'footprint': 0.0 },
            { 'az': 'region-1a', 'itype': 'c4.medium', 'family': 'c4', 'size': 'medium', 'count': 0.5, 'footprint': 1.0 },
            { 'az': 'region-1a', 'itype': 'c4.large',  'family': 'c4', 'size': 'large',  'count': 0.0, 'footprint': 0.0 },
            { 'az': 'region-1b', 'itype': 'c4.small',  'family': 'c4', 'size': 'small',  'count': 0.0, 'footprint': 0.0 },
            { 'az': 'region-1b', 'itype': 'c4.medium', 'family': 'c4', 'size': 'medium', 'count': 1.0, 'footprint': 2.0 },
            { 'az': 'region-1b', 'itype': 'c4.large',  'family': 'c4', 'size': 'large',  'count': 0.0, 'footprint': 0.0 },
        ])
        self.assertEqual(unused_instances.dump(), [
            { 'az': 'region', 'itype': 'c4.large', 'family': 'c4', 'size': 'large', 'count': 0.0, 'footprint': 0.0 },
        ])

        # hyblid
        running_instances  = aws_ec2_count.Instances()
        running_instances.get('region-1a', 'c4', 'medium').set_count(10) # footprint = 20
        running_instances.get('region-1a', 'c4', 'large').set_count(4)   # footprint = 12
        running_instances.get('region-1a', 'c4', 'xlarge').set_count(5)
        running_instances.get('region-1b', 'c4', 'medium').set_count(4)  # footprint =  8
        running_instances.get('region-1b', 'c4', 'large').set_count(2)
        running_instances.get('region-1b', 'c4', 'xlarge').set_count(10)
        reserved_instances = aws_ec2_count.Instances()
        reserved_instances.get('region',    'c4', 'xlarge').set_count(10)
        reserved_instances.get('region-1a', 'c4', 'xlarge').set_count(10)
        reserved_instances.get('region-1b', 'c4', 'xlarge').set_count(5)
        ondemand_instances, unused_instances = fetcher.get_ondemand_instances(running_instances, reserved_instances)
        self.assertEqual(ondemand_instances.dump(), [
            { 'az': 'region-1a', 'itype': 'c4.medium', 'family': 'c4', 'size': 'medium', 'count': 0.0, 'footprint':  0.0 },
            { 'az': 'region-1a', 'itype': 'c4.large',  'family': 'c4', 'size': 'large',  'count': 1.0, 'footprint':  4.0 },
            { 'az': 'region-1a', 'itype': 'c4.xlarge', 'family': 'c4', 'size': 'xlarge', 'count': 0.0, 'footprint':  0.0 },
            { 'az': 'region-1b', 'itype': 'c4.medium', 'family': 'c4', 'size': 'medium', 'count': 0.0, 'footprint':  0.0 },
            { 'az': 'region-1b', 'itype': 'c4.large',  'family': 'c4', 'size': 'large',  'count': 2.0, 'footprint':  8.0 },
            { 'az': 'region-1b', 'itype': 'c4.xlarge', 'family': 'c4', 'size': 'xlarge', 'count': 0.0, 'footprint':  0.0 },
        ])
        self.assertEqual(unused_instances.dump(), [
            { 'az': 'region',    'itype': 'c4.xlarge', 'family': 'c4', 'size': 'xlarge', 'count': 0.0, 'footprint':  0.0 },
            { 'az': 'region-1a', 'itype': 'c4.xlarge', 'family': 'c4', 'size': 'xlarge', 'count': 5.0, 'footprint': 40.0 },
            { 'az': 'region-1b', 'itype': 'c4.xlarge', 'family': 'c4', 'size': 'xlarge', 'count': 0.0, 'footprint':  0.0 },
        ])

class TestAWSEC2InstanceCounter(unittest.TestCase):
    def test_dummy(self):
        self.assertTrue(True)


