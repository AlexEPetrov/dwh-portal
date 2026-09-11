Feature: curve calculator

    Scenario Outline: Calculating curve values for time series
        Given I have curve definition
            """
            {
                "name": "ECB_EURUSD",
                "type": "curve",
                "point_interval": "business_day",
                "uom": "USD/EUR",
                "calendar": "ecb"
            }
            """
        And the curve "ECB_EURUSD" contains values
            | report_date | observ_date | value |
            | 2025-01-01  | 2025-01-01  | 1.041 |
            | 2025-01-02  | 2025-01-02  | 1.042 |
            | 2025-01-03  | 2025-01-03  | 1.043 |
            | 2025-01-04  | 2025-01-04  | 1.044 |
            | 2025-01-05  | 2025-01-05  | 1.045 |
            | 2025-01-06  | 2025-01-06  | 1.046 |
            | 2025-01-07  | 2025-01-07  | 1.047 |
            | 2025-01-08  | 2025-01-08  | 1.048 |
            | 2025-01-09  | 2025-01-09  | 1.049 |
            | 2025-01-10  | 2025-01-10  | 1.051 |
            | 2025-01-11  | 2025-01-11  | 1.052 |
            | 2025-01-12  | 2025-01-12  | 1.053 |
            | 2025-01-13  | 2025-01-13  | 1.054 |
            | 2025-01-14  | 2025-01-14  | 1.055 |
            | 2025-01-15  | 2025-01-15  | 1.056 |
            | 2025-01-16  | 2025-01-16  | 1.041 |
            | 2025-01-17  | 2025-01-17  | 1.042 |
            | 2025-01-18  | 2025-01-18  | 1.043 |
            | 2025-01-19  | 2025-01-19  | 1.044 |
            | 2025-01-20  | 2025-01-20  | 1.045 |
            | 2025-01-21  | 2025-01-21  | 1.046 |
            | 2025-01-22  | 2025-01-22  | 1.047 |
            | 2025-01-23  | 2025-01-23  | 1.048 |
            | 2025-01-24  | 2025-01-24  | 1.049 |
            | 2025-01-25  | 2025-01-25  | 1.051 |
            | 2025-01-26  | 2025-01-26  | 1.052 |
            | 2025-01-27  | 2025-01-27  | 1.053 |
            | 2025-01-28  | 2025-01-28  | 1.054 |
            | 2025-01-29  | 2025-01-29  | 1.055 |
            | 2025-01-30  | 2025-01-30  | 1.056 |          
            | 2025-01-31  | 2025-01-31  | 1.056 |  

        When the curve <curve> is calculated at valuation date <val_date> and observation date <obs_date> with aggregation options <aggregation>
        Then the value is <expected_value>

        Examples: curve elements
            | curve      | val_date   | obs_date   | aggregation                                                                                                     | expected_value |
            | ECB_EURUSD | 2025-02-15 | 2025-02-15 | {'type': "offset",'offset_unit': "month", 'offset_from': -1, 'offset_to': -1, 'offset_point': "valuation_date"} | 1.041          |
            # | ECB_EURUSD | 2025-02-15 | 2025-01-01 | {}                                                                                                              | 200.0          |
            # | ECB_EURUSD | 2025-02-15 | 2025-01-01 | {}                                                                                                              | 200.0          |
            # | ECB_EURUSD | 2025-02-15 | 2025-01-01 | {}                                                                                                              | 200.0          |
            # | ECB_EURUSD | 2025-02-15 | 2025-01-01 | {}                                                                                                              | 200.0          |
