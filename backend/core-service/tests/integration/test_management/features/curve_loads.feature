# Feature: Loading curves
#         I logged in to price management service
#         I have empty service configuration   
#         I have standard dwh configuration and data

#     Scenario: Load curve values from datasource
#         Given I have object with properties:
#             | name                 | value                  |
#             | name                 | TTF_DA                 |
#             | type                 | curve                  |
#             | calendar             | argus_european_nat_gas |
#             | category             | Market-GAS             |
#             | curve_type           | spot                   |
#             | data_source          | None                   |
#             | dwh_data_params      | hub=TTF;ticker=DA      |
#             | dwh_data_source      | queries/argus.sql      |
#             | dwh_data_source_type | query                  |
#             | point_interval       | business_day           |
#             | slug                 | TTF_DA                 |
#             | uom                  | EUR/Mwh                |

#         When I send a POST request to "/api/management/curves" with params:
#         |body||
#         |f||
#         Then the response status code should be 201
#         And the response should contain the created user data