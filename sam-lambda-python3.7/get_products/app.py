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

def get_all_products(database_config):
    connection = mysql.connector.connect(**database_config)
    cursor = connection.cursor()
    cursor.execute("SELECT * FROM Product;")
    products = cursor.fetchall()
    cursor.close()
    connection.close()

    product_list = []
    for product in products:
        product_dict = {
            "rowId": product[0],
            "productId": product[1],
            "productName": product[2],
            "productCategory": product[3],
            "productPrice": product[4],
            "productImageUrl": product[5],
            "productDescription": product[6],
            "productWeight": product[7]
        }
        product_list.append(product_dict)

    return product_list

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

    all_products = get_all_products(database_config)
    response = {
                'body': json.dumps(all_products)
            }
            
    json_data = json.loads(response['body'])
    return json_data

