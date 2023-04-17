import boto3
from botocore.exceptions import ClientError
import os
import json
import mysql.connector

def get_secret():

    secret_name = "db_order_scp"
    region_name = "us-east-1"

    # Create a Secrets Manager client
    session = boto3.session.Session()
    client = session.client(
        service_name='secretsmanager',
        region_name=region_name
    )

    try:
        get_secret_value_response = client.get_secret_value(
            SecretId=secret_name
        )
    except ClientError as e:
        # For a list of exceptions thrown, see
        # https://docs.aws.amazon.com/secretsmanager/latest/apireference/API_GetSecretValue.html
        raise e

    # Decrypts secret using the associated KMS key.
    secret = get_secret_value_response['SecretString']

    return secret

def verifyOrderCode(database_config, event):
    connection = mysql.connector.connect(**database_config)
    cursor = connection.cursor()
    order_number = event["orderNumber"]
    order_code = event["orderCode"]

    sql_select_query = "SELECT orderCode FROM UserOrder WHERE orderNumber=%s"
    cursor.execute(sql_select_query, (order_number,))
    result = cursor.fetchone()

    cursor.close()
    connection.close()

    if result is None:
        return {
            "message": "Order not found."
        }

    stored_order_code = result[0]
    
    if order_code == stored_order_code:
        return {
            "message": "Order Code matches."
        }
    else:
        return {
            "message": "Order Code does not match."
        }

def lambda_handler(event, context):
    database_config_str = get_secret()
    database_config = json.loads(database_config_str)
    print("db cred:", database_config)
    # Remove the unsupported 'engine' argument
    # Remove the unsupported arguments
    unsupported_keys = ['engine', 'dbInstanceIdentifier']
    for key in unsupported_keys:
        if key in database_config:
            del database_config[key]

    result = verifyOrderCode(database_config, event)
    response = {
                'body': json.dumps(result)
            }
            
    json_data = json.loads(response['body'])
    return json_data

