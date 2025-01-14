# -*- coding: utf-8 -*-

import json
import unittest

from botocore.exceptions import ClientError

from localstack.utils.aws import aws_stack
from localstack.utils.common import to_str

TEST_TOPIC_NAME = 'TestTopic_snsTest'
TEST_QUEUE_NAME = 'TestQueue_snsTest'


class SNSTest(unittest.TestCase):

    def setUp(self):
        self.sqs_client = aws_stack.connect_to_service('sqs')
        self.sns_client = aws_stack.connect_to_service('sns')
        self.topic_arn = self.sns_client.create_topic(Name=TEST_TOPIC_NAME)['TopicArn']
        self.queue_url = self.sqs_client.create_queue(QueueName=TEST_QUEUE_NAME)['QueueUrl']

    def tearDown(self):
        self.sqs_client.delete_queue(QueueUrl=self.queue_url)
        self.sns_client.delete_topic(TopicArn=self.topic_arn)

    def test_publish_unicode_chars(self):
        # connect the SNS topic to the SQS queue
        queue_arn = aws_stack.sqs_queue_arn(TEST_QUEUE_NAME)
        self.sns_client.subscribe(TopicArn=self.topic_arn, Protocol='sqs', Endpoint=queue_arn)

        # publish message to SNS, receive it from SQS, assert that messages are equal
        message = u'ö§a1"_!?,. £$-'
        self.sns_client.publish(TopicArn=self.topic_arn, Message=message)
        msgs = self.sqs_client.receive_message(QueueUrl=self.queue_url)
        msg_received = msgs['Messages'][0]
        msg_received = json.loads(to_str(msg_received['Body']))
        msg_received = msg_received['Message']
        self.assertEqual(message, msg_received)

    def test_attribute_raw_subscribe(self):
        # create SNS topic and connect it to an SQS queue
        queue_arn = aws_stack.sqs_queue_arn(TEST_QUEUE_NAME)
        self.sns_client.subscribe(
            TopicArn=self.topic_arn,
            Protocol='sqs',
            Endpoint=queue_arn,
            Attributes={'RawMessageDelivery': 'true'}
        )

        # fetch subscription information
        subscription_list = self.sns_client.list_subscriptions()

        subscription_arn = ''
        for subscription in subscription_list['Subscriptions']:
            if subscription['TopicArn'] == self.topic_arn:
                subscription_arn = subscription['SubscriptionArn']
        actual_attributes = self.sns_client.get_subscription_attributes(SubscriptionArn=subscription_arn)['Attributes']

        # assert the attributes are well set
        self.assertTrue(actual_attributes['RawMessageDelivery'])

        # publish message to SNS, receive it from SQS, assert that messages are equal and that they are Raw
        message = u'This is a test message'
        self.sns_client.publish(TopicArn=self.topic_arn, Message=message)

        msgs = self.sqs_client.receive_message(QueueUrl=self.queue_url)
        msg_received = msgs['Messages'][0]
        self.assertEqual(message, msg_received['Body'])

    def test_unknown_topic_publish(self):
        fake_arn = 'arn:aws:sns:us-east-1:123456789012:i_dont_exist'
        message = u'This is a test message'
        try:
            self.sns_client.publish(TopicArn=fake_arn, Message=message)
            self.fail('This call should not be successful as the topic does not exist')
        except ClientError as e:
            self.assertEqual(e.response['Error']['Code'], 'NotFound')
            self.assertEqual(e.response['Error']['Message'], 'Topic does not exist')
            self.assertEqual(e.response['ResponseMetadata']['HTTPStatusCode'], 404)

    def test_publish_sms(self):
        response = self.sns_client.publish(PhoneNumber='+33000000000', Message='This is a SMS')
        self.assertTrue('MessageId' in response)
        self.assertEqual(response['ResponseMetadata']['HTTPStatusCode'], 200)
