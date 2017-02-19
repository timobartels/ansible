#!/usr/bin/python

import logging
import marathon
import requests
from marathon.exceptions import InternalServerError, NotFoundError
from marathon.exceptions import MarathonHttpError, MarathonError
from marathon.models.events import EventFactory
from marathon import MarathonClient
from marathon.models import MarathonApp, MarathonDeployment, MarathonGroup
from marathon.models import MarathonInfo, MarathonTask
from marathon.models import MarathonEndpoint, MarathonQueueItem
from ansible.module_utils.basic import *
dependencies_missing = False
dependencies_message = ""
try:
    import json
    import jsonschema
    import requests
except ImportError as err:
    dependencies_missing = True
    dependencies_message = str(err.args[0])


DOCUMENTATION = '''
---
module: marathon_deploy
short_description: Deploy a docker image on DCOS/Marathon scheduler
description:
  - Deploys a docker image in Enterprise or Open Mesosphere / DCOS platform.
  - The application configuration may be provided inline using supported
    configuration options below or using a JSON file.

version_added: "1.0"

options:
  url:
    description:
      - Mesosphere / DCOS Controller URL
    required: true
  user:
    description:
      - User id for authentication
    required: true
  password:
    description:
      - User password
    required: true
  app_config:
    description:
      - Marathon app config json as dict
    required: true
'''


class DcosMarathon(MarathonClient):

    def _is_reachable(self, url):
        try:
            response = requests.get(url)
            response.raise_for_status()
            return True
        except requests.exceptions.HTTPError as err:
            return True
        except:
            pass
        return False

    def _token(self, force_new=False):
        if self.dcos is False:
            return None
        if self.auth_token is not None and not force_new:
            return self.auth_token
        data = '{"uid": "%s", "password": "%s"}' % (self.user, self.password)
        headers = {'Content-Type': 'application/json',
                   'Accept': 'application/json'}
        response = requests.post(self.url.rstrip(
            "/") + "/acs/api/v1/auth/login", data=data, headers=headers)
        response.raise_for_status()
        return response.json()['token']

    def __init__(self, url, username=None, password=None, timeout=10,
                 dcos=True):
        self.marathon_url = url
        if dcos is True:
            self.marathon_url = "%s/marathon" % (url)
        super(DcosMarathon, self).__init__(self.marathon_url,
                                           username=username,
                                           password=password, timeout=timeout)
        self.url, self.user, self.password,\
            self.dcos = url, username, password, dcos
        self.auth_token = None
        self.can_connect, self.auth_token = self._is_reachable(
            self.marathon_url), self._token(force_new=True)

    def __str__(self):
        mode, status = "dcos", "unknown"

        if self.dcos is False:
            mode = "standalone"

        if self.auth_token is not None:
            status = "authenticated"
        if self.can_connect is True:
            status = "reachable"

        return "url: %s, mode: %s, status: %s" % (
                self.marathon_url, mode, status)

    def _do_request(self, method, path, params=None, data=None):
        """Query Marathon server."""
        headers = {'Content-Type': 'application/json',
                   'Accept': 'application/json'}
        if self.dcos is True:
            headers['Authorization'] = "token=%s" % (self._token())
            self.auth = None
        response = None
        servers = list(self.servers)
        while servers and response is None:
            server = servers.pop(0)
            url = ''.join([server.rstrip('/'), path])
            try:
                logging.info(data)
                logging.info(url)
                logging.info(headers)
                response = self.session.request(
                    method, url, params=params, data=data, headers=headers,
                    auth=self.auth, timeout=self.timeout)
                marathon.log.info('Got response from %s', server)
            except requests.exceptions.RequestException as e:
                marathon.log.error(
                    'Error while calling %s: %s', url, str(e))

        if response is None:
            raise MarathonError('No remaining Marathon servers to try')

        if response.status_code >= 500:
            marathon.log.error('Got HTTP {code}: {body}'.format(
                code=response.status_code, body=response.text))
            raise InternalServerError(response)
        elif response.status_code >= 400:
            marathon.log.error('Got HTTP {code}: {body}'.format(
                code=response.status_code, body=response.text))
            if response.status_code == 404:
                raise NotFoundError(response)
            else:
                raise MarathonHttpError(response)
        elif response.status_code >= 300:
            marathon.log.warn('Got HTTP {code}: {body}'.format(
                code=response.status_code, body=response.text))
        else:
            marathon.log.debug('Got HTTP {code}: {body}'.format(
                code=response.status_code, body=response.text))

        return response

    def _do_sse_request(self, path, params=None, data=None):
        from sseclient import SSEClient

        headers = {'Accept': 'text/event-stream'}
        if self.dcos is True:
            headers['Authorization'] = "token=%s" % (self._token())
            self.auth = None
        messages = None
        servers = list(self.servers)
        while servers and messages is None:
            server = servers.pop(0)
            url = ''.join([server.rstrip('/'), path])
            try:
                messages = SSEClient(url, params=params, data=data,
                                     headers=headers, auth=self.auth)
            except Exception as e:
                marathon.log.error(
                    'Error while calling %s: %s', url, e.message)

        if messages is None:
            raise MarathonError('No remaining Marathon servers to try')

        return messages


def main():
    logging.basicConfig(level=logging.WARN, format='%(levelname)s %(message)s')
    module = AnsibleModule(
        argument_spec=dict(
            url=dict(required=True),
            user=dict(required=True),
            password=dict(required=True),
            app_config=dict(required=True, type='dict')
        ),
        supports_check_mode=True
    )

    if dependencies_missing:
        module.fail_json(changed=False, msg=dependencies_message)

    client = DcosMarathon(module.params['url'], module.params[
                          'user'], module.params['password'], 30, True)
    response = deploy_app(client, module.params['app_config'])
    module.exit_json(changed=True, meta={"response": response})


def change_app_config(app_config):
    app_config['instances'] = int(app_config['instances'])
    app_config['cpus'] = float(app_config['cpus'])
    app_config['mem'] = int(app_config['mem'])
    return app_config


def deploy_app(client, app_config):
    return client.update_app(
        app_config['id'], MarathonApp(**change_app_config(app_config)), True)

if __name__ == '__main__':
    main()
