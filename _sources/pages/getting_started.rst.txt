Getting started
===============
When it comes to ``discord.http``, it is not like the usual websocket bots.
This library is only for the ``HTTP POST`` requests sent by the Discord API.
You can of course use this library to do normal Discord actions, however you do not have some familiar intents, like:

- Able to see the guilds the bot is in
- Knowing then the bot joins/leaves a server
- Status changes to people or bots

Essentially, no intents are available, however there are some you do get, which are:

- Whenever a slash command is used
- When someone clicks a button, selects in menu, etc
- When someone has submitted a modal

Requirements
------------

Python
~~~~~~
First of all you need Python to be installed, you can get `python here <https://www.python.org/downloads/>`_.
We recommend that you use Python 3.11 or higher, lower versions may not work.

After that, you need to install the library, you can do so by using ``pip install discord.http`` in the terminal.

.. note::
  Some systems might have ``pip3`` instead of ``pip``, if that is the case,
  use ``pip3 install discord.http`` instead. In some rare cases if that does not work,
  try ``python -m pip install discord.http`` or ``python3 -m pip install discord.http``.

HTTP Server
~~~~~~~~~~~
Depending on the approach you take, there are multiple ways to host the HTTP server.
For local testing, you can use `ngrok <https://ngrok.com/>`_,
which is a tool that allows you to expose your local server to the internet.

Planning to host this in a server on production scale?
You can use `Apache2 <https://httpd.apache.org/>`_ or `NGINX <https://www.nginx.com/>`_.
For beginners, Apache2 is a nice way to get introduced to hosting, however we recommend
using NGINX due to its performance overall and its ability to handle more requests.

Quick example
-------------
After installing everything, you can make a very simple ``/ping`` bot with the following code:

.. include:: ../../README.md
  :start-after: <!-- DOCS: quick_example -->
  :end-before: ```
  :literal:


By default, the library will be hosting on ``127.0.0.1`` to prevent external access
while using the port ``8080``. You're free to change it to your liking, but be careful
if you choose to use ``0.0.0.0`` and only use it if you know what you are doing.

After booting up your bot, next step will be to register the chosen URL
in to your `bot's application page <https://discord.com/developers/applications>`_.
Inside the bot configuration page, you will see a section called "Interactions Endpoint URL",
paste your URL there and save the settings.

The URL you past in there is the root URL, there's no need to add ``/interactions`` or similar to the end of it.
So if your domain is ``example.com``, you put that inside the bot's interaction URL setting.

.. image:: ../_static/images/getting_started/interaction_url.png

.. note::
  If the page refuses to save, it means that your bot is not exposed to the correct URL.
  Discord attempts to ping with the URL you provided, and if it fails, it will not save.

  If the Discord developer page saved successfully, you should see your bot printed an ``[ INFO ]`` message
  telling what has happened. This simply means that you did it all correctly and can now start using the bot.

3rd-party tools
----------------

gunicorn
~~~~~~~~
Planning to scale your bot to multiple workers? You can use `gunicorn <https://gunicorn.org/>`_.
Since this library is built on top of ``Quart``, which is essentially ``Flask``, but with async, you can use gunicorn.

If we take the example bot code above, you can start doing so by using the following command:

.. code-block:: bash

  gunicorn filename:client.backend

Remember to replace ``filename`` with whatever your root file is called. It could be ``main.py``, ``bot.py`` or similar.
In those two cases, you would use ``gunicorn main:client.backend`` and ``gunicorn bot:client.backend`` respectively.


Hosting examples
--------------------

ngrok
~~~~~
This is the most simple approach to hosting a HTTP server,
however if you plan to use this as a hosting method for production,
you will need to upgrade to their paid plan to get a static URL with no limits.

However for local testing, you can use the free plan, which will give you a randomly generated URL.
You can get `ngrok here <https://ngrok.com/download>`_ and follow the instructions on their website.

After downloading it, you need to open a new terminal and run the command ``ngrok http 8080``.
Keep in mind that the bot has to also run on port 8080, otherwise you will need to change
the port in the command mentioned earlier.

NGINX
~~~~~

.. code-block:: nginx

    # You need to replace example.com with your own domain of choice
    # or remove it if you plan to use IP like http://123.123.123.123 (not recommended)

    # You will also need to change the proxy_pass to whatever local address and port you are using

    # HTTPS Example
    server {
      listen 443 ssl http2;
      listen [::]:443 ssl http2;
      server_name example.com;

      location / {
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header Host $http_host;
        proxy_set_header X-Forwarded-Proto https;
        proxy_redirect off;
        proxy_pass http://localhost:8080;
        proxy_http_version 1.1;
      }

      ssl on;
      ssl_verify_client on;
    }

    # HTTP Example
    server {
      listen 80;
      listen [::]:80;
      server_name example.com;

      location / {
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header Host $http_host;
        proxy_set_header X-Forwarded-Proto https;
        proxy_redirect off;
        proxy_pass http://localhost:8080;
        proxy_http_version 1.1;
      }
    }

Apache2
~~~~~~~

.. code-block:: apache

    # You need to replace example.com with your own domain of choice
    # or remove it if you plan to use IP like http://123.123.123.123 (not recommended)

    # You will also need to change both ProxyPass and ProxyPassReverse
    # to whatever local address and port you are using

    # HTTPS Example
    <VirtualHost *:443>
        ServerName example.com

        SSLEngine on
        SSLVerifyClient require

        SSLProxyEngine on
        SSLProxyVerify require
        SSLProxyCheckPeerCN on
        SSLProxyCheckPeerName on
        SSLProxyCheckPeerExpire on

        ProxyPass / http://localhost:8080/
        ProxyPassReverse / http://localhost:8080/

        <Proxy *>
            Order deny,allow
            Allow from all
        </Proxy>

        RequestHeader set X-Forwarded-Proto "https"
        RequestHeader set X-Forwarded-For "%{X-Forwarded-For}e"
        RequestHeader set Host "%{Host}i"

    </VirtualHost>

    # HTTP Example
    <VirtualHost *:80>
        ServerName example.com

        ProxyPass / http://localhost:8080/
        ProxyPassReverse / http://localhost:8080/

        <Proxy *>
            Order deny,allow
            Allow from all
        </Proxy>

        RequestHeader set X-Forwarded-Proto "https"
        RequestHeader set X-Forwarded-For "%{X-Forwarded-For}e"
        RequestHeader set Host "%{Host}i"

    </VirtualHost>
