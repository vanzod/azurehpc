# Copyright 2013-2020 Lawrence Livermore National Security, LLC and other
# Spack Project Developers. See the top-level COPYRIGHT file for details.
#
# SPDX-License-Identifier: (Apache-2.0 OR MIT)

"""This file contains the definition of the Azure Blob storage Class used to integrate Azure Blob storage with spack buildcache.
"""

import os
import sys
import datetime
from pathlib import Path

import llnl.util.tty as tty

class AzureBlob:
    def __init__(self, url):
        from azure.storage.blob import BlobServiceClient
        self.url = url
        (self.container_name, self.blob_path) = self.get_container_blob_path()
        if url.scheme != 'azure':
           raise ValueError(
            'Can not create Azure blob connection from URL with scheme: {SCHEME}'.format(
                SCHEME=url.scheme))
        if "AZURE_STORAGE_CONNECTION_STRING" in os.environ:
           self.connect_str = os.environ.get('AZURE_STORAGE_CONNECTION_STRING')
           self.blob_service_client = BlobServiceClient.from_connection_string(self.connect_str)
           if not self.azure_container_exists():
              tty.warn("The container {} does not exist, it will be created".format(self.container_name))
              self.blob_service_client.create_container(self.container_name)
        else:
           tty.error("Error: Environmental variable AZURE_STORAGE_CONNECTION_STRING is not defined, it is required if you want to use Azure Blob storage as an spack buildcache")
           sys.exit(1)

    def get_container_blob_path(self):
        blob_path = self.url.path
        p = Path(blob_path)
        container_name = p.parts[1]
        blob_path = str(Path(*p.parts[2:]))
        tty.debug("container_name = {}, blob_path = {}".format(container_name, blob_path))
        return (container_name, blob_path)


    def is_https(self):
        if 'https' in self.connect_str:
           return True
        else:
           return False


    def azure_container_exists(self):
        try:
           ttt = self.blob_service_client.get_container_client(self.container_name).list_blobs()
           for blob in ttt:
               pass
        except Exception as ex:
            return False
        return True


    def azure_blob_exists(self):
        try:
           blob_client = self.blob_service_client.get_blob_client(container=self.container_name, blob=self.blob_path)
           blob_properties = blob_client.get_blob_properties()
        except Exception as ex:
            return False
        return True


    def azure_delete_blob(self):
        try:
           blob_client = (self.blob_service_client.
                          get_blob_client(container=self.container_name,
                                          blob=self.blob_path))
           blob_client.delete_blob()
        
        except Exception as ex:
           tty.error("{}, Could not delete azure blob {}".format(ex, self.blob_path))
 

    def azure_upload_to_blob(self, local_file_path):
        from azure.storage.blob import ContentSettings
        if Path(self.blob_path).suffix == '.json':
           contentsettings = ContentSettings(content_type="application/json")
        else:
           contentsettings = ContentSettings()
        try:
           blob_client = self.blob_service_client.get_blob_client(container=self.container_name, blob=self.blob_path)
           with open(local_file_path, "rb") as data:
               blob_client.upload_blob(data, overwrite=True, content_settings=contentsettings)
        except Exception as ex:
           tty.error("{}, Could not upload {} to azure blob storage".format(ex, local_file_path))


    def azure_list_blobs(self):
        try:
           container_client = self.blob_service_client.get_container_client(self.container_name)
           blob_gen = container_client.list_blobs()
           blob_list=[]
           for blob in blob_gen:
               p = blob.name.split('/')
               build_cache_index = p.index('build_cache')
               blob_list.append(os.path.join(*p[build_cache_index + 1:]))
           return blob_list
        except Exception as ex:
           tty.error("{}, Could not get a list of azure blobs".format(ex))            


    def azure_url_sas(self):
        from azure.storage.blob import ResourceTypes, AccountSasPermissions, generate_account_sas
        try:
           sas_token = generate_account_sas(self.blob_service_client.account_name, 
                       account_key=self.blob_service_client.credential.account_key, 
                       resource_types=ResourceTypes(object=True), permission=AccountSasPermissions(read=True), 
                       expiry=datetime.datetime.utcnow() + datetime.timedelta(minutes=5))
        except Exception as ex:
           tty.error("{}, Could not generate a sas token for Azure blob storage".format(ex))
        url_str = self.url.geturl()
        url_str = url_str.replace('azure', 'https', 1)
        url_sas_str = url_str + '?' + sas_token 
        return url_sas_str
