package com.fintech.loans.legacy.client;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestTemplate;

import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * LEGACY — Hand-rolled SOAP 1.1 client to the credit bureau.
 *
 * PROBLEM: XML envelope built by string concatenation — applicantId is not
 *          escaped (XML injection); no schema validation either way.
 * PROBLEM: response parsed with a regex — a namespace prefix change or
 *          whitespace reformat at the bureau breaks scoring silently.
 * PROBLEM: RestTemplate, blocking, no timeout tuning, no retry/breaker —
 *          bureau latency spikes stall the whole origination flow.
 *
 * MIGRATE TO (fintech-soap-to-rest): the bureau's REST v2 API behind a typed
 * anti-corruption layer (BureauScorePort) with WebClient + Resilience4j.
 */
@Component
public class CreditBureauSoapClient {

    private static final Logger log = LoggerFactory.getLogger(CreditBureauSoapClient.class);

    private static final Pattern SCORE_PATTERN =
            Pattern.compile("<(?:\\w+:)?CreditScore>(\\d+)</(?:\\w+:)?CreditScore>");

    private final RestTemplate restTemplate = new RestTemplate();

    @Value("${bureau.soap.url:http://localhost:9998/bureau/soap}")
    private String bureauUrl;

    public int fetchCreditScore(String applicantId) {
        // PROBLEM: unescaped interpolation into XML
        String envelope =
                "<?xml version=\"1.0\" encoding=\"UTF-8\"?>"
                + "<soapenv:Envelope xmlns:soapenv=\"http://schemas.xmlsoap.org/soap/envelope/\" "
                + "xmlns:bur=\"http://bureau.example.com/credit\">"
                + "<soapenv:Header/>"
                + "<soapenv:Body>"
                + "<bur:GetCreditScoreRequest>"
                + "<bur:ApplicantId>" + applicantId + "</bur:ApplicantId>"
                + "</bur:GetCreditScoreRequest>"
                + "</soapenv:Body>"
                + "</soapenv:Envelope>";

        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.TEXT_XML);
        headers.set("SOAPAction", "GetCreditScore");

        String response = restTemplate.postForObject(bureauUrl, new HttpEntity<>(envelope, headers), String.class);

        Matcher matcher = SCORE_PATTERN.matcher(response == null ? "" : response);
        if (!matcher.find()) {
            // PROBLEM: parse failure indistinguishable from "no file" at the bureau
            log.error("Could not parse CreditScore from bureau response");
            return -1;
        }
        return Integer.parseInt(matcher.group(1));
    }
}
