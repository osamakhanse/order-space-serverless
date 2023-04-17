import boto3
from botocore.exceptions import ClientError
import os
import json
import mysql.connector
import random


def generate_random_code(length=4):
    return ''.join([str(random.randint(0, 9)) for _ in range(length)])
    
    
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

def generate_order_number(row_id):
    return f"ORD{row_id:04d}"

def create_order(database_config, event):
    connection = mysql.connector.connect(**database_config)
    cursor = connection.cursor()

    # UserOrder data
    order_data = event["orderData"]
    order_datetime = order_data["orderDateTime"]
    order_total = order_data["orderTotal"]
    order_status = order_data["orderStatus"]
    order_code = generate_random_code()
    rider_id = order_data["riderId"]
    rider_name = order_data["riderName"]
    rider_time_slot = order_data["riderTimeSlot"]
    user_name = order_data["userName"]
    totalWeight = order_data["totalWeight"]

    # OrderProducts data
    order_products = event["orderProducts"]

    try:
        # Insert order into UserOrder table
        insert_order_query = '''
        INSERT INTO UserOrder (orderDateTime, orderTotal, orderStatus, orderCode, riderId, riderName, riderTimeSlot, userName, totalWeight)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        '''
        cursor.execute(insert_order_query, (order_datetime, order_total, order_status, order_code, rider_id, rider_name, rider_time_slot, user_name, totalWeight))
        connection.commit()
        row_id = cursor.lastrowid  # Get the rowId of the inserted order
        order_number = generate_order_number(row_id)

        # Update the orderNumber in the UserOrder table
        update_order_number_query = "UPDATE UserOrder SET orderNumber = %s WHERE rowId = %s"
        cursor.execute(update_order_number_query, (order_number, row_id))
        connection.commit()

        # Insert order products into OrderProduct table
        insert_order_product_query = '''
        INSERT INTO OrderProduct (orderProductId, productId, quantity, orderProductDescription, totalPrice, unitPrice, productImageUrl, productName)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        '''
        for order_product in order_products:
            cursor.execute(insert_order_product_query, (order_number, order_product["productId"], order_product["quantity"], order_product["orderProductDescription"], order_product["totalPrice"], order_product["unitPrice"], order_product["productImageUrl"],  order_product["productName"]))
            connection.commit()
        
        orderResponse = {
            'orderNumber' : order_number
        }
        response = {
            'statusCode': 200,
            'body': json.dumps(orderResponse)
        }

    except Exception as e:
        print(f"ERROR: Could not create the order. {e}")
        response = {
            'statusCode': 500,
            'body': json.dumps('An error occurred while creating the order.')
        }

    finally:
        cursor.close()
        connection.close()

    return response


def update_order(database_config, event):
    connection = mysql.connector.connect(**database_config)
    cursor = connection.cursor()

    order_id = event["orderNumber"]
    updated_attributes = event["updatedAttributes"]

    sql_update_query = "UPDATE UserOrder SET "
    query_params = []

    for attribute, value in updated_attributes.items():
        if attribute in ["orderStatus"]:
            sql_update_query += f"{attribute}=%s, "
            query_params.append(value)

    sql_update_query = sql_update_query.rstrip(', ')  # Remove the last comma and space
    sql_update_query += " WHERE orderNumber=%s"
    query_params.append(order_id)

    try:
        cursor.execute(sql_update_query, tuple(query_params))
        connection.commit()
    except Exception as e:
        print(f"ERROR: Could not update the order. {e}")
        return {
            'statusCode': 500,
            'body': json.dumps('An error occurred while updating the order.')
        }
    finally:
        cursor.close()
        connection.close()

    return "Order " + order_id +" updated successfully."

def get_order(database_config, order_number):
    connection = mysql.connector.connect(**database_config)
    cursor = connection.cursor()

    try:
        # Get order details from UserOrder table
        cursor.execute("SELECT * FROM UserOrder WHERE orderNumber = %s", (order_number,))
        order_result = cursor.fetchone()

        if order_result:
            # Get the column names from the cursor description
            column_names = [column[0] for column in cursor.description]

            # Create a dictionary from the fetched order details
            order_details = {column_names[i]: value for i, value in enumerate(order_result)}

            # Get order products from OrderProduct table
            cursor.execute("SELECT * FROM OrderProduct WHERE orderProductId = %s", (order_number,))
            order_products_result = cursor.fetchall()

            # Create a list of dictionaries for order products
            order_products = []
            if order_products_result:
                # Get the column names from the cursor description
                product_column_names = [column[0] for column in cursor.description]

                for product_result in order_products_result:
                    product_details = {product_column_names[i]: value for i, value in enumerate(product_result)}
                    order_products.append(product_details)

            # Add the order products to the order_details dictionary
            order_details["orderProducts"] = order_products

            response = {
                'statusCode': 200,
                'body': json.dumps(order_details)
            }

        else:
            response = {
                'statusCode': 404,
                'body': json.dumps('Order not found')
            }

    except Exception as e:
        print(f"ERROR: Could not get the order. {e}")
        response = {
            'statusCode': 500,
            'body': json.dumps('An error occurred while getting the order.')
        }

    finally:
        cursor.close()
        connection.close()

    return response


def get_orders_by_user(database_config, user_name):
    connection = mysql.connector.connect(**database_config)
    cursor = connection.cursor()

    try:
        # Get orders from UserOrder table
        cursor.execute("SELECT * FROM UserOrder WHERE userName = %s order by rowId Desc" , (user_name,))
        orders_result = cursor.fetchall()

        if orders_result:
            # Get the column names from the cursor description
            column_names = [column[0] for column in cursor.description]

            # Create a list of dictionaries for orders
            orders = []
            for order_result in orders_result:
                order_details = {column_names[i]: value for i, value in enumerate(order_result)}

                # Get order products from OrderProduct table
                order_number = order_details['orderNumber']
                cursor.execute("SELECT * FROM OrderProduct WHERE orderProductId = %s", (order_number,))
                order_products_result = cursor.fetchall()

                # Create a list of dictionaries for order products
                order_products = []
                if order_products_result:
                    # Get the column names from the cursor description
                    product_column_names = [column[0] for column in cursor.description]

                    for product_result in order_products_result:
                        product_details = {product_column_names[i]: value for i, value in enumerate(product_result)}
                        order_products.append(product_details)

                # Add the order products to the order_details dictionary
                order_details["orderProducts"] = order_products
                orders.append(order_details)

            response = {
                'statusCode': 200,
                'body': json.dumps(orders)
            }

        else:
            response = {
                'statusCode': 404,
                'body': json.dumps('No orders found for the user')
            }

    except Exception as e:
        print(f"ERROR: Could not get orders for the user. {e}")
        response = {
            'statusCode': 500,
            'body': json.dumps(f'An error occurred while getting orders for the user: {str(e)}')
        }


    finally:
        cursor.close()
        connection.close()

    return response


def lambda_handler(event, context):
    action = event['action']
    if action not in ['create_order', 'update_order', 'get_order', 'get_orders_by_user']:
        return {
            'statusCode': 400,
            'body': json.dumps('Invalid action')
        }

    database_config_str = get_secret()
    database_config = json.loads(database_config_str)
    print("db cred:", database_config)
    # Remove the unsupported arguments
    unsupported_keys = ['engine', 'dbInstanceIdentifier']
    for key in unsupported_keys:
        if key in database_config:
            del database_config[key]

    if action == 'create_order':
        response = create_order(database_config, event)
    elif action == 'update_order':
        response = update_order(database_config, event)
    elif action == 'get_order':
        response = get_order(database_config, event['orderNumber'])
    elif action == 'get_orders_by_user':
        response = get_orders_by_user(database_config, event['userName'])
            
    json_data = json.loads(response['body'])
    return json_data

