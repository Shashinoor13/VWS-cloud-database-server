#!/usr/bin/env python3

# ===============================================================================
# Copyright (c) 2024 PTC Inc., Its Subsidiary Companies, and /or its Partners.
# All Rights Reserved.
#
# Vuforia is a trademark of PTC Inc., registered in the United States and other
# countries.
# ===============================================================================

"""
Vuforia Engine Cloud Recognition target management API.
"""

import sys
import logging
import argparse
from pathlib import Path
import json
import hashlib
import hmac
import base64
from email.utils import formatdate
from pprint import pprint
from urllib.parse import urlparse

import requests
from requests import Request, Response, PreparedRequest
from requests.auth import AuthBase

logger = logging.getLogger(__name__)


class VwsAuthentication(AuthBase):
    """Authenticate VWS requests."""

    def __init__(self, access_key: str, secret_key: str):
        self.access_key: str = access_key
        self.secret_key: str = secret_key

    def __call__(self, request: PreparedRequest) -> PreparedRequest:
        route = urlparse(request.url).path
        method = request.method
        content = request.body if request.body is not None else b""

        if not isinstance(content, bytes):
            raise ValueError("Expected binary content in request")

        date = formatdate(None, localtime=False, usegmt=True)

        # Ensure the content type is an empty string if body is empty
        content_type = request.headers.get("Content-Type", "")
        if (len(content) == 0) and len(content_type) > 0:
            raise ValueError("Content-Type header must not be specified when request body is empty.")
        request.headers["Content-Type"] = content_type

        # VWS signature is computed on the content-type without boundary in multipart/form-data requests
        content_type_bare = content_type.split(";")[0]

        authorization_header = VwsAuthentication._authorization_header(self.access_key, self.secret_key, method,
                                                                       content, content_type_bare, date, route)
        request.headers["Authorization"] = authorization_header
        request.headers["Date"] = date
        request.headers["Content-Type"] = content_type
        logger.debug(request.headers)

        request.headers["Authorization"] = authorization_header
        return request

    @staticmethod
    def _compute_md5_hex(data: bytes) -> str:
        """Return the hex MD5 of the data"""
        h = hashlib.md5()
        h.update(data)
        return h.hexdigest()

    @staticmethod
    def _compute_hmac_base64(key: str, data: str) -> str:
        """Return the Base64 encoded HMAC-SHA1 using the provide key"""
        h = hmac.new(key.encode(), None, hashlib.sha1)
        h.update(data.encode())
        return base64.b64encode(h.digest()).decode()

    @staticmethod
    def _authorization_header(access_key: str, secret_key: str, method: str, content: bytes, content_type: str, date: str, request_path: str) -> str:
        """Return the value of the Authorization header for the request parameters"""
        components_to_sign = list()
        components_to_sign.append(method.upper())
        components_to_sign.append(str(VwsAuthentication._compute_md5_hex(content)))
        components_to_sign.append(content_type)
        components_to_sign.append(date)
        components_to_sign.append(request_path)
        string_to_sign = "\n".join(components_to_sign)
        signature = VwsAuthentication._compute_hmac_base64(secret_key, string_to_sign)
        auth_header = "VWS %s:%s" % (access_key, signature)
        return auth_header


class VuforiaVwsClient:
    headers: dict[str, str] = {"User-Agent": "VuforiaVwsClientPython/1.0"}

    def __init__(self, api_base: str, access_key: str, secret_key: str):
        self.api_base: str = api_base
        self.vws_authentication = VwsAuthentication(access_key, secret_key)

    def post(self, route: str, **kwargs) -> Response:
        return self._request("post", route, **kwargs)

    def put(self, route: str, **kwargs) -> Response:
        return self._request("put", route, **kwargs)

    def delete(self, route: str, **kwargs) -> Response:
        return self._request("delete", route, **kwargs)

    def get(self, route: str, **kwargs) -> Response:
        return self._request("get", route, **kwargs)

    def _request(self, method: str, route: str, **kwargs) -> Response:
        url = f"{self.api_base}{route}"
        response = requests.request(method=method, url=url, auth=self.vws_authentication, **kwargs)
        return response

    @staticmethod
    def ensure_success(response: Response, success="Success") -> Response:
        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            print(response.status_code, response.reason)
            pprint(response.text)
            raise e

        try:
            response_json = response.json()
        except requests.exceptions.JSONDecodeError as e:
            print(response.status_code, response.reason)
            pprint(response.text)
            raise e

        if response_json["result_code"] != success:
            raise Exception(response_json)

        print(json.dumps(response_json, indent=2))
        return response


class CloudQueryWebAPIClient:
    def __init__(self, vws_client: VuforiaVwsClient):
        self.vws_client = vws_client

    def query(self, image: Path, max_num_results: int = 1, include_target_data: str = "top") -> Response:
        response = self.vws_client.post(
            "/v1/query",
            files=[("image", (image.name, open(image, "rb"), "application/octet-stream"))],
            data={
                "max_num_results": max_num_results,
                "include_target_data": include_target_data,
            },
        )
        return self.vws_client.ensure_success(response)


class CloudTargetWebAPIClient:
    def __init__(self, vws_client: VuforiaVwsClient):
        self.vws_client = vws_client

    def create_target(self, image: Path, name: str, width: float, metadata_base64: str | None,
                      active: bool | None) -> Response:
        logger.info(f"Creating Cloud Reco Target '{name}' from {image}...")
        image_base64 = base64.b64encode(open(image, "rb").read()).decode()
        data = {
            "name": name,
            "image": image_base64,
            "width": width,
        }

        if metadata_base64 is not None:
            data["application_metadata"] = metadata_base64

        if active is not None:
            data["active_flag"] = active

        response = self.vws_client.post(
            "/targets",
            data=json.dumps(data).encode(),
            headers={"Content-Type": "application/json"},
        )
        return self.vws_client.ensure_success(response, success="TargetCreated")

    def get_target(self, target_id: str) -> Response:
        response = self.vws_client.get(f"/targets/{target_id}")
        return self.vws_client.ensure_success(response)

    def update_target(self, target_id: str, image: Path | None, name: str | None, width: float | None,
                      metadata_base64: str | None, active: bool | None) -> Response:
        logger.info(f"Updating Cloud Reco Target '{target_id}'...")
        data = {}

        if image is not None:
            image_base64 = base64.b64encode(open(image, "rb").read()).decode()
            data["image"] = image_base64

        if name is not None:
            data["name"] = name

        if width is not None:
            data["width"] = width

        if metadata_base64 is not None:
            data["application_metadata"] = metadata_base64

        if active is not None:
            data["active_flag"] = active

        response = self.vws_client.put(
            f"/targets/{target_id}",
            data=json.dumps(data).encode(),
            headers={"Content-Type": "application/json"},
        )
        return self.vws_client.ensure_success(response)

    def delete_target(self, target_id: str) -> Response:
        response = self.vws_client.delete(f"/targets/{target_id}")
        return self.vws_client.ensure_success(response)

    def list_targets(self) -> Response:
        response = self.vws_client.get("/targets")
        return self.vws_client.ensure_success(response)

    def get_target_report(self, target_id: str) -> Response:
        response = self.vws_client.get(f"/summary/{target_id}")
        return self.vws_client.ensure_success(response)

    def get_database_report(self) -> Response:
        response = self.vws_client.get("/summary")
        return self.vws_client.ensure_success(response)

    def get_duplicates(self, target_id: str) -> Response:
        response = self.vws_client.get(f"/duplicates/{target_id}")
        return self.vws_client.ensure_success(response)


def string_to_boolean(v: str) -> bool:
    if v.lower() in ("yes", "true", "1"):
        return True
    elif v.lower() in ("no", "false", "0"):
        return False
    else:
        raise argparse.ArgumentTypeError(f"Boolean value expected.  Received: {v}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Cloud Target Web API client")

    parser.add_argument('--environment', type=str, help=argparse.SUPPRESS, default="production")
    parser.add_argument("--access-key", type=str, help="The VWS server or client access key", required=True)
    parser.add_argument("--secret-key", type=str, help="The VWS server or client secret key", required=True)
    parser.add_argument("--verbose", "-v", action="count", default=0,
                        help="Enable detailed logging. Repeat the option for more verbose logging.")

    subparsers = parser.add_subparsers(dest="command", help="Action to execute on the API")

    download_command = subparsers.add_parser("get", help="Get information about a specific target")
    download_command.add_argument("target_id", type=str, help="ID of the target")

    create_command = subparsers.add_parser("create", help="Create a Cloud Target")
    create_command.add_argument("--image", type=Path, help="Path to the source image in JPG or PNG format", required=True)
    create_command.add_argument("--name", type=str, help="Name of the created target", required=True)
    create_command.add_argument("--width", type=float, help="The width of the target in scene units", required=True)
    create_command.add_argument("--metadata-base64", type=str, default=None,
                                help="The base64 encoded application metadata associated with the target")
    create_command.add_argument("--active", type=string_to_boolean, default=None,
                                help="Whether or not the target is active for query")

    update_command = subparsers.add_parser("update", help="Update a Cloud Target")
    update_command.add_argument("target_id", type=str, help="ID of the target")
    update_command.add_argument("--image", type=Path, default=None,
                                help="Path to the new source image in JPG or PNG format")
    update_command.add_argument("--name", type=str, default=None, help="The updated Name of the target")
    update_command.add_argument("--width", type=float, default=None,
                                help="The updated width of the target in scene units")
    update_command.add_argument("--metadata-base64", type=str, default=None,
                                help="The updated base64 encoded application metadata")
    update_command.add_argument("--active", type=string_to_boolean, default=None,
                                help="Whether or not the updated target is active for query")

    delete_command = subparsers.add_parser("delete", help="Deletes Cloud Target with all the associated artifacts")
    delete_command.add_argument("target_id", type=str, help="Id of the target to delete")

    _ = subparsers.add_parser("list", help="List all Cloud Reco Targets")

    get_target_report_command = subparsers.add_parser("get-target-report", help="Get the target summary report")
    get_target_report_command.add_argument("target_id", type=str, help="ID of the target")

    _ = subparsers.add_parser("get-database-report", help="Get the database summary report")

    get_duplicates_command = subparsers.add_parser("get-duplicates",
                                                   help="Search the database for duplicate and similar images")
    get_duplicates_command.add_argument("target_id", type=str, help="ID of the target")

    query_command = subparsers.add_parser("query", help="Query a Cloud Target database")
    query_command.add_argument("--image", type=Path, help="Path to the query image in JPG or PNG format", required=True)
    query_command.add_argument("--max-num-results", type=int, default=1,
                                help="the maximum number of matching targets to be returned")

    args = parser.parse_args(args=None if sys.argv[1:] else ["--help"])

    if args.verbose > 0:
        if args.verbose == 1:
            logging.basicConfig(level=logging.INFO)
        else:
            logging.basicConfig(level=logging.DEBUG)

    ## Environment flag only used for internal PTC testing
    if args.environment == "production":
        query_url = "https://cloudreco.vuforia.com"
        provisioning_url = "https://vws.vuforia.com"
    else:
        env_info = json.load(open("environments.json"))[args.environment]
        query_url = env_info["query_url"]
        provisioning_url = env_info["provisioning_url"]

    if args.command == "query":
        vws_client = VuforiaVwsClient(query_url, args.access_key, args.secret_key)
        client = CloudQueryWebAPIClient(vws_client)

        client.query(
            image=args.image,
            max_num_results=args.max_num_results,
        )
    else:
        vws_client = VuforiaVwsClient(provisioning_url, args.access_key, args.secret_key)
        client = CloudTargetWebAPIClient(vws_client)

        if args.command == "create":
            client.create_target(
                image=args.image,
                name=args.name,
                width=args.width,
                metadata_base64=args.metadata_base64,
                active=args.active,
            )
        elif args.command == "get":
            client.get_target(args.target_id)
        if args.command == "update":
            client.update_target(
                target_id=args.target_id,
                image=args.image,
                name=args.name,
                width=args.width,
                metadata_base64=args.metadata_base64,
                active=args.active,
            )
        elif args.command == "delete":
            client.delete_target(args.target_id)
        elif args.command == "list":
            client.list_targets()
        elif args.command == "get-target-report":
            client.get_target_report(args.target_id)
        elif args.command == "get-database-report":
            client.get_database_report()
        elif args.command == "get-duplicates":
            client.get_duplicates(args.target_id)


if __name__ == "__main__":
    main()
