from setuptools import setup, find_packages
import os

version = '2.1.0.dev19+auction.worker.sharding'
install_requires = [
    'setuptools',
    'openprocurement.auction.worker',
    'requests',
    'APScheduler',
    'iso8601',
    'python-dateutil',
    'Flask',
    'WTForms',
    'WTForms-JSON',
    'Flask-Redis',
    'WSGIProxy2',
    'gevent',
    'sse',
    'flask_oauthlib',
    'Flask-Assets',
    'cssmin',
    'jsmin',
    'PyYAML',
    'request_id_middleware',
    'restkit',
    'PyMemoize',
    'barbecue',
    # ssl warning
    'pyopenssl',
    'ndg-httpsclient',
    'pyasn1',
    'openprocurement_client',
    'python-consul',
    'retrying',
    'zope.interface',
    'walkabout'
]
extras_require = {
    'test': [
        'robotframework',
        'robotframework-selenium2library',
        'robotframework-debuglibrary',
        'robotframework-selenium2screenshots',
        'chromedriver',
        'mock'
    ]
}
entry_points = {
    'console_scripts': [
        'auctions_chronograph = openprocurement.auction.chronograph:main',
        'auctions_data_bridge = openprocurement.auction.databridge:main',
        'auction_test = openprocurement.auction.tests.main:main [test]'
    ],
    'paste.app_factory': [
        'auctions_server = openprocurement.auction.auctions_server:make_auctions_app',
    ],
    'openprocurement.auction.auctions': [
        'default = openprocurement.auction.includeme:includeme',
        'belowThreshold = openprocurement.auction.includeme:includeme',
        'aboveThresholdUA = openprocurement.auction.includeme:includeme',
        'aboveThresholdEU = openprocurement.auction.includeme:includeme',
        'competitiveDialogueEU.stage2 = openprocurement.auction.includeme:includeme',
        'competitiveDialogueUA.stage2 = openprocurement.auction.includeme:includeme',
        'aboveThresholdUA.defense = openprocurement.auction.includeme:includeme',
    ]
}

setup(name='openprocurement.auction',
      version=version,
      description="",
      long_description=open("README.txt").read() + "\n" +
                       open(os.path.join("docs", "HISTORY.txt")).read(),
      # Get more strings from
      # http://pypi.python.org/pypi?:action=list_classifiers
      classifiers=[
        "License :: OSI Approved :: Apache Software License",
        "Programming Language :: Python",
      ],
      keywords='',
      author='Quintagroup, Ltd.',
      author_email='info@quintagroup.com',
      license='Apache License 2.0',
      url='https://github.com/openprocurement/openprocurement.auction',
      packages=find_packages(exclude=['ez_setup']),
      namespace_packages=['openprocurement'],
      include_package_data=True,
      zip_safe=False,
      install_requires=install_requires,
      extras_require=extras_require,
      entry_points=entry_points,
      )
