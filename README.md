# The Threaded Bristol Stock Exchange (TBSE)

[![Python version: 3.4+](https://img.shields.io/badge/python-3.4+-blue.svg)](https://www.python.org/download/releases/3.4.0/)
[![](https://img.shields.io/github/issues/MichaelRol/Threaded-Bristol-Stock-Exchange)](https://github.com/MichaelRol/Threaded-Bristol-Stock-Exchange/issues)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)


TBSE is an extension of Dave Cliff's (University of Bristol) [Bristol Stock Exchange (BSE)](https://github.com/davecliff/BristolStockExchange "Bristol Stock Exchange") limit order-book financial exchange simulator. Originally created for my MEng dissertation it has since been used in [Rollins & Cliff (2020)](https://arxiv.org/abs/2009.06905) and [Cliff & Rollins (2020)](https://arxiv.org/abs/2011.14346).

TBSE simulates a CDA market where different automated trading algorithms can be compared under a variety of market conditions. The key difference between TBSE and BSE is that TBSE makes use of Python's multi-threading library which allows traders to operate asynchronously of each other and of the exchange, which is a more realistic model of real-world financial exchanges. This allows the execution time of the trading algorithms to have in impact on their performance. 

Also included in this repository is a copy of BSE which has been updated to Python3. A guide to BSE, much of which also applies to TBSE, can be found [here.](https://github.com/davecliff/BristolStockExchange/blob/master/BSEguide1.2e.pdf "BSE Guide")
## Usage

TBSE, if unedited, can be ran with the following terminal command:

```console
$ python3 TBSE.py
```

There is a section of code in TBSE which has been 'commented-out', that, if uncommented, can allow for a CSV input file to be named. A more user-friendly implementation of this will be included in the next release. 

The [BSE Guide](https://github.com/davecliff/BristolStockExchange/blob/master/BSEguide1.2e.pdf "BSE Guide") can be used for a guide to configuring market sessions in both BSE and TBSE. 

## License
The code is open-sourced via the [MIT](http://opensource.org/licenses/mit-license.php) Licence: see the LICENSE file for full text. 
