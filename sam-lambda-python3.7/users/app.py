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


def get_user_detail(cursor, user_name):
    cursor.execute("SELECT * FROM User WHERE userName = %s", (user_name,))
    result = cursor.fetchone()

    if result:
        user_dict = {
            "rowId": result[0],
            "userName": result[1],
            "userAddress": result[2],
            "userPhoneNumber": result[3],
            "userEmail": result[4],
            "userCountry": result[5],
            "name": result[6],
        }
        return user_dict
    else:
        return {
            'statusCode': 404,
            'body': json.dumps('User not found')
        }

def edit_user_detail(cursor, user_data):
    user_name = user_data.pop('userName')
    
    for key, value in user_data.items():
        cursor.execute("UPDATE User SET " + key + " = %s WHERE userName = %s", (value, user_name))

    return {
        'statusCode': 200,
        'body': json.dumps(f'User details updated for userName: {user_name}')
    }

def lambda_handler(event, context):
    action = event['action']
    user_data = event['user_data']

    if action not in ['get_user_detail', 'edit_user_detail']:
        return {
            'statusCode': 400,
            'body': json.dumps('Invalid action')
        }

    try:
        database_config_str = get_secret()
        database_config = json.loads(database_config_str)
        print("db cred:", database_config)
        # Remove the unsupported 'engine' argument
        # Remove the unsupported arguments
        unsupported_keys = ['engine', 'dbInstanceIdentifier']
        for key in unsupported_keys:
            if key in database_config:
                del database_config[key]
        connection = mysql.connector.connect(**database_config)
        cursor = connection.cursor()
        if action == 'get_user_detail':
            user_name = user_data['userName']
            response = get_user_detail(cursor, user_name)
        elif action == 'edit_user_detail':
            response = edit_user_detail(cursor, user_data)
            connection.commit()

        cursor.close()
        connection.close()
        apiResponse = {
                    'body': json.dumps(response)
                }
                
        json_data = json.loads(apiResponse['body'])
        return json_data

    except Exception as e:
        return {
            'statusCode': 500,
            'body': json.dumps(str(e))
        }
