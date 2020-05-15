import json
import os
import boto3
import email
import re
from botocore.exceptions import ClientError
from email.parser import BytesParser
from email import policy

from sms_spam_classifier_utilities import one_hot_encode
from sms_spam_classifier_utilities import vectorize_sequences


vocabulary_length = 9013

def query_S3(bucket, objkey):
    s3 = boto3.resource('s3')
    bucket = s3.Bucket(bucket)
    body = "";
    for obj in bucket.objects.all():
        key = obj.key
        if key==objkey:
            body = obj.get()['Body'].read()
    # print(body)
    return body

def parse_body(body):
    """
        Parse the body from the email and extract the required fields. 
        Need to extract sender email, subject of the email, the receive date, and body of the email.
    """
    msg = BytesParser(policy=policy.SMTP).parsebytes(body)
    print("This is the message: ", msg.keys())
    print("From : ",msg['From'])
    print("Date: ",msg['Date'])
    print("To: ",msg['To'])
    print("Subject : ",msg['Subject'])
    plain = ''
    try:
        plain = msg.get_body(preferencelist=('plain'))
        plain = ''.join(plain.get_content().splitlines(keepends=True))
        plain = '' if plain == None else plain
    except:
        print('Incoming message does not have an plain text part - skipping this part.')
        
    return {
        'from': msg['From'],
        'to': msg['To'],
        'subject': msg['Subject'],
        'date': msg['Date'],
        'text':plain
        }


def hit_sagemaker(text):
    """
        Hit sagemaker endpoint with text and get response. Return the confidence and other information.
    """
    ENDPOINT_NAME = "sms-spam-classifier-mxnet-2020-05-12-05-34-38-136"
    runtime= boto3.client('runtime.sagemaker')
    vocabulary_length = 9013
    
    test_messages = [text]
    
    one_hot_test_messages = one_hot_encode(test_messages, vocabulary_length)
    encoded_test_messages = vectorize_sequences(one_hot_test_messages, vocabulary_length)
    response = runtime.invoke_endpoint(EndpointName=ENDPOINT_NAME, ContentType='application/json', Body=json.dumps(encoded_test_messages.tolist()))
    return response['Body'].read().decode('UTF-8')
    pass

def process_response(info, smresp):
    """
        Take text and return the message in the format given in the text. Can use json.
    """
    label = 'spam'
    if smresp['predicted_label'][0][0] == 0.0:
        label = 'ham'
    confidence = smresp['predicted_probability'][0][0]
    if label=='ham':
        confidence = 1-confidence
    print(label, confidence)
    message = "We received your email sent at "+str(info['date'])+" with the subject: "+str(info['subject'])+"Here is a 240 character sample of the email body: "+str(info['text'])+".The email was categorized as "+str(label)+" with a "+str(confidence*100)+"% confidence."
    
    print(message)
    return message
    pass

def send_email(email, message):
    """
        Send the 'message' to the 'email' as given in the assignment. Get the email from the body of the email.
    """
    SENDER = email['to']

    # Replace recipient@example.com with a "To" address. If your account 
    # is still in the sandbox, this address must be verified.
    RECIPIENT = "anjanragh@gmail.com"
    # RECIPIENT = email['from']
    
    # RECIPIENT = RECIPIENT[RECIPIENT.find('<')+1:-1]
    print("Receipent: ", RECIPIENT);
    
    # Specify a configuration set. If you do not want to use a configuration
    # set, comment the following variable, and the 
    # ConfigurationSetName=CONFIGURATION_SET argument below.
    #CONFIGURATION_SET = "ConfigSet"
    
    # If necessary, replace us-west-2 with the AWS Region you're using for Amazon SES.
    AWS_REGION = "us-west-2"
    
    # The subject line for the email.
    SUBJECT = email['subject']
    
    # The email body for recipients with non-HTML email clients.
    # BODY_TEXT = (message)
    BODY_TEXT = ("Response text")
                
    # The HTML body of the email.
    # BODY_HTML = """<html>
    # <head></head>
    # <body>
    #   <h1>CloudTeam: Amazon SES Response</h1>
    #   <p>We received your email sent at "+str(info['date'])+" with the subject: "+str(info['subject'])+"Here is a 240 character sample of the email body: "+str(info['text'])+".The email was categorized as "+str(label)+" with a "+str(confidence*100)+"% confidence.</p>
    # </body>
    # </html>
    #             """            
    
    # The character encoding for the email.
    CHARSET = "UTF-8"
    
    # Create a new SES resource and specify a region.
    client = boto3.client('ses',region_name=AWS_REGION)
    
    # Try to send the email.
    try:
        #Provide the contents of the email.
        sndmessage = {"Subject" : {"Data" : SUBJECT}, "Body" : {"Html":{"Data": message}}}
        print(SENDER,"Is the sender ")
        resp = client.send_email(Source = SENDER, Destination = {"ToAddresses":[RECIPIENT]},Message = sndmessage)
        # response = client.send_email(
        #     Destination={
        #         'ToAddresses': [
        #             RECIPIENT,
        #         ],
        #     },
        #     Message={
        #         'Body': {
        #             'Html': {
        #                 'Charset': CHARSET,
        #                 'Data': BODY_TEXT,
        #             },
        #             # 'Text': {
        #             #     'Charset': CHARSET,
        #             #     'Data': BODY_TEXT,
        #             # },
        #         },
        #         'Subject': {
        #             'Charset': CHARSET,
        #             'Data': SUBJECT,
        #         },
        #     },
        #     Source=SENDER,
        #     # If you are not using a configuration set, comment or delete the
        #     # following line
        #     #ConfigurationSetName=CONFIGURATION_SET,
        # )
    # Display an error if something goes wrong.	
    except ClientError as e:
        print(e.response['Error']['Message'])
    else:
        print("Email sent! Message ID:"),
        # print(response['MessageId'])
    pass

def cleanup(text):
    text = text.replace('\n', ' ').replace('\r', '').replace('-','').replace(',','')
    text = ' '.join(text.split())
    return text
    
    
def lambda_handler(event, context):
    # TODO implement
    event = {'Records': [{'eventVersion': '2.1', 'eventSource': 'aws:s3', 'awsRegion': 'us-west-2', 'eventTime': '2020-05-12T03:50:43.027Z', 'eventName': 'ObjectCreated:Put', 'userIdentity': {'principalId': 'AWS:AIDAJF4DQJXXZUH7QKSIS'}, 'requestParameters': {'sourceIPAddress': '10.89.88.183'}, 'responseElements': {'x-amz-request-id': '2CF2DF797DEC0403', 'x-amz-id-2': 'LmGz4arQihqb25Wuwk0n8FlkWCPaT7d5nd8/tsOAvCqIkewKoXqFx6lVnLjNsSg07hEaghmAlW5/89y+ky8ZvJXnRpgQDFrg'}, 's3': {'s3SchemaVersion': '1.0', 'configurationId': 'MyEmailEventForPut', 'bucket': {'name': 'myemailbucketcc', 'ownerIdentity': {'principalId': 'AM280O3UQ70R'}, 'arn': 'arn:aws:s3:::myemailbucketcc'}, 'object': {'key': 'enllvtjmf7qcvl3cnkniqhns7rfp26ejasf8rco1', 'size': 5892, 'eTag': '9e70054347237eeedc4a4df4552328bb', 'sequencer': '005EBA1D1402382E04'}}}]}
    # print("***************")
    # print(event)
    # print("***************")
    bucket = event["Records"][0]["s3"]["bucket"]["name"]
    objkey = event["Records"][0]["s3"]["object"]["key"]
    
    
    email_obj = parse_body(query_S3(bucket, objkey))
    # print("This is the text: ",text)
    text = email_obj['text']
    text = cleanup(text)
    print("This is the new text: ",text)
    
    # response = json.loads(hit_sagemaker(text))
    # print(response)
    # print("sagemaker response:",response)
    # finalmessage = process_response(email_obj, response)
    
    finalmessage = "Hello from the other side"
    send_email(email_obj, finalmessage)
    
    return {
        'statusCode': 200,
        'body': json.dumps('Hello from Lambda!')
    }

