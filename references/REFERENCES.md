# References

The grounding behind the model: the real-world problem the engine addresses, and
the operations-research methods it implements from scratch.

## The problem (why it is real, and the part that is unsolved)

Quick commerce in India is a large, fast-growing market that still loses money on
most orders, and the losses concentrate outside the big metros. These sources are
the calibration anchors in `data/qcom_financials_fy26.csv`.

- IndMoney, "How much are Zepto, Blinkit, Instamart losing per order, and can they
  ever be profitable" - per-order loss and the profitability question (Blinkit
  -Rs 3.02, Zepto -Rs 78.75, Instamart -Rs 85.18 in FY26).
  https://www.indmoney.com/blog/stocks/zepto-blinkit-instamart-loss-per-order-profitability
- "Quick Commerce Unit Economics 2026 (Blinkit / Zepto / Instamart)" - loss-per-order,
  AOV, and the dark-store profitability split.
  https://globalwebsters.com/blog/quick-commerce-unit-economics-blinkit-zepto-instamart/
- GlobeNewswire, "India Quick Commerce Report 2026" - market size, the six-player
  structure, and dark-store counts.
  https://www.globenewswire.com/news-release/2026/04/20/3277255/28124/en/india-quick-commerce-report-2026-market-to-reach-12-97-billion-by-2029-blinkit-zepto-and-swiggy-instamart-lead-surge-as-jiomart-and-bigbasket-scale-competitive-entry.html
- StartupFeed, "Quick Commerce War 2026" - market shares and the "unit economics,
  not 10 minutes" framing.
  https://startupfeed.in/quick-commerce-war-2026-blinkit-zepto-instamart-amazon-flipkart/
- Mordor Intelligence, "India Q-commerce market size / share / outlook" - market
  structure anchor.
  https://www.mordorintelligence.com/industry-reports/q-commerce-industry-in-india

The open part: comparative P&L analyses of Blinkit vs Zepto already exist. What is
missing is a structural model connecting the spatial drivers (density, order
arrival rate, travel times, batching) to per-order contribution margin, and then
locating the lever combination that crosses breakeven in the tier-2 density regime.
That is what this engine builds.

## The methods (the operations-research spine)

Most of these are classical operations-research results, cited by DOI. The one
freely redistributable paper (SALib, open access) is included as a PDF.

- Discrete-event simulation and M/M/c queueing. The dark store is modelled as
  arrivals into a finite-server picking queue plus a rider dispatch stage. Standard
  references: Banks, Carson, Nelson and Nicol, "Discrete-Event System Simulation";
  Kleinrock, "Queueing Systems, Volume 1: Theory" (1975).
- Non-homogeneous Poisson process via thinning. Lewis and Shedler, "Simulation of
  nonhomogeneous Poisson processes by thinning", Naval Research Logistics Quarterly,
  1979. doi:10.1002/nav.3800260304
- Huff gravity / retail-catchment model. Huff, "Defining and Estimating a Trading
  Area", Journal of Marketing, 1964. doi:10.2307/1249154
- p-median and maximal-covering facility location. ReVelle and Swain, "Central
  facilities location", Geographical Analysis, 1970, doi:10.1111/j.1538-4632.1970.tb00142.x;
  Church and ReVelle, "The maximal covering location problem", Papers in Regional
  Science, 1974, doi:10.1111/j.1435-5597.1974.tb00902.x. The LP relaxation bound is
  the standard linear relaxation of the covering integer program.
- Nelder-Mead derivative-free simplex optimization. Nelder and Mead, "A simplex
  method for function minimization", The Computer Journal, 1965.
  doi:10.1093/comjnl/7.4.308
- Sobol global sensitivity analysis (variance-based attribution). Sobol,
  "Global sensitivity indices for nonlinear mathematical models and their Monte
  Carlo estimates", Mathematics and Computers in Simulation, 2001,
  doi:10.1016/S0378-4754(00)00270-6; the Jansen total-effect estimator, Jansen,
  "Analysis of variance designs for model output", Computer Physics Communications,
  1999, doi:10.1016/S0010-4655(98)00154-4; Saltelli et al., "Variance based
  sensitivity analysis of model output", Computer Physics Communications, 2010,
  doi:10.1016/j.cpc.2009.09.018.
- SALib (implementation reference for the Saltelli sampling and Sobol estimators,
  re-implemented here from scratch). Herman and Usher, "SALib: An open-source Python
  library for Sensitivity Analysis", Journal of Open Source Software, 2017.
  doi:10.21105/joss.00097. PDF: `salib_joss_2017.pdf`.

## Files in this folder

- `salib_joss_2017.pdf` - the SALib paper (open access, CC-BY), the reference for the
  from-scratch Sobol / Saltelli implementation in `qcom/sensitivity.py`.
