import httplib
import hashlib
import hmac
import base64
from email.utils import formatdate
import json
import sys

# The hostname of the Vuforia Web Services API
VWS_HOSTNAME='vws.vuforia.com'


def compute_md5_hex(data):
    """Return the hex MD5 of the data"""
    h = hashlib.md5()
    h.update(data)
    return h.hexdigest()


def compute_hmac_base64(key, data):
    """Return the Base64 encoded HMAC-SHA1 using the provide key"""
    h = hmac.new(key, None, hashlib.sha1)
    h.update(data)
    return base64.b64encode(h.digest())


def authorization_header_for_request(access_key, secret_key, method, content, content_type, date, request_path):
    """Return the value of the Authorization header for the request parameters"""
    components_to_sign = list()
    components_to_sign.append(method)
    components_to_sign.append(str(compute_md5_hex(content)))
    components_to_sign.append(str(content_type))
    components_to_sign.append(str(date))
    components_to_sign.append(str(request_path))
    string_to_sign = "\n".join(components_to_sign)
    signature = compute_hmac_base64(secret_key, string_to_sign)
    auth_header = "VWS %s:%s" % (access_key, signature)
    return auth_header


def request_instance(access_key, secret_key, target_uuid, instance_id, output_format):
    """Make an HTTPS request to create a VuMark instance and return the HTTP status code and body"""
    http_method = 'POST'
    date = formatdate(None, localtime=False, usegmt=True)
    content_type = 'application/json'
    path = "/targets/%s/instances" % target_uuid

    # The body of the request is JSON and contains one attribute, the instance ID of the VuMark
    content = {"instance_id": instance_id}
    request_body = json.dumps(content)

    # Sign the request and get the Authorization header
    auth_header = authorization_header_for_request(access_key, secret_key, http_method, request_body, content_type,
                                                   date, path)
    request_headers = {
        'Accept': output_format,
        'Authorization': auth_header,
        'Content-Type': content_type,
        'Date': date
    }

    # Make the request over HTTPS on port 443
    http = httplib.HTTPSConnection(VWS_HOSTNAME, 443)
    http.request(http_method, path, request_body, request_headers)

    response = http.getresponse()
    response_body = response.read()
    return response.status, response_body

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Generate a single instance of a VuMark')
    parser.add_argument('--access-key', required=True, type=str, help='The access key for the VuMark database')
    parser.add_argument('--secret-key', required=True, type=str, help='The secret key for the VuMark database')
    parser.add_argument('--target-id', required=True, type=str, help='The UUID of the VuMark target')
    parser.add_argument('--instance-id', required=True, type=str, help='The ID of the instance to create')
    parser.add_argument('--format', required=False, type=str,
                        default='image/svg+xml', choices=['image/svg+xml','image/png','image/jpg','application/pdf'],
                        help='The output format of the instance')
    args = parser.parse_args()

    status, body = request_instance(access_key=args.access_key,
                                    secret_key=args.secret_key,
                                    target_uuid=args.target_id,
                                    instance_id=args.instance_id,
                                    output_format=args.format)
    if status == 200:
        print body
        sys.exit(0)
    else:
        print status
        print body
        sys.exit(status)
