package com.fintech.loans.legacy.service;

import com.fintech.loans.legacy.client.CreditBureauSoapClient;
import com.fintech.loans.legacy.model.LoanApplication;
import com.fintech.loans.legacy.model.LoanDecision;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

import java.util.UUID;

/**
 * LEGACY — Monolithic credit decisioning.
 *
 * Problems this class demonstrates:
 *
 *   1. decide() mixes bureau I/O, affordability maths and policy thresholds
 *      in one method — none of it independently testable or reusable
 *   2. Credit policy as hardcoded constants — score cut-offs and DTI limits
 *      require a release to change; risk team cannot iterate
 *   3. Bureau parse failure (-1) handled as a magic number threading through
 *      the decision logic
 *   4. No decision audit: inputs, thresholds applied and outcome are not
 *      recorded anywhere queryable
 *
 * Modernisation (fintech-soap-to-rest + fintech-java-spring2-to-spring3):
 *   - BureauScorePort anti-corruption layer over the REST v2 bureau API
 *   - Policy externalised to a versioned decision table
 *   - Affordability calculator as a pure, property-tested function
 *   - Every decision emitted as an immutable audit event with policy version
 */
@Service
public class LoanDecisionService {

    private static final Logger log = LoggerFactory.getLogger(LoanDecisionService.class);

    // PROBLEM: credit policy frozen in code
    private static final int DECLINE_BELOW_SCORE = 560;
    private static final int REFER_BELOW_SCORE = 640;
    private static final double MAX_DEBT_TO_INCOME = 0.45;
    private static final double BASE_APR = 6.9;
    private static final double SUBPRIME_APR_LOADING = 5.0;

    private final CreditBureauSoapClient bureauClient;

    public LoanDecisionService(CreditBureauSoapClient bureauClient) {
        this.bureauClient = bureauClient;
    }

    public LoanDecision decide(LoanApplication application) {
        String requestId = UUID.randomUUID().toString();

        // I/O in the middle of decision logic — must be mocked to test anything
        int bureauScore = bureauClient.fetchCreditScore(application.getApplicantId());

        // PROBLEM: -1 magic number for "bureau parse failed / no file"
        if (bureauScore < 0) {
            log.warn("No bureau score for applicant {} — referring", application.getApplicantId());
            return new LoanDecision("REFERRED", 0.0, bureauScore, requestId);
        }

        if (bureauScore < DECLINE_BELOW_SCORE) {
            return new LoanDecision("DECLINED", 0.0, bureauScore, requestId);
        }

        // Affordability — double arithmetic on money throughout
        double monthlyRepayment = estimateMonthlyRepayment(
                application.getRequestedAmount(), application.getTermMonths(), BASE_APR);
        double debtToIncome = application.getMonthlyIncome() <= 0
                ? 1.0
                : (application.getMonthlyDebtRepayments() + monthlyRepayment) / application.getMonthlyIncome();

        if (debtToIncome > MAX_DEBT_TO_INCOME) {
            return new LoanDecision("DECLINED", 0.0, bureauScore, requestId);
        }

        if (bureauScore < REFER_BELOW_SCORE) {
            // Near-prime: human underwriter queue, subprime pricing if approved
            return new LoanDecision("REFERRED", BASE_APR + SUBPRIME_APR_LOADING, bureauScore, requestId);
        }

        log.info("Approved applicant {} requestId={} score={}",
                application.getApplicantId(), requestId, bureauScore);
        return new LoanDecision("APPROVED", BASE_APR, bureauScore, requestId);
    }

    private double estimateMonthlyRepayment(double principal, int termMonths, double apr) {
        double monthlyRate = apr / 100.0 / 12.0;
        return principal * monthlyRate / (1 - Math.pow(1 + monthlyRate, -termMonths));
    }
}
