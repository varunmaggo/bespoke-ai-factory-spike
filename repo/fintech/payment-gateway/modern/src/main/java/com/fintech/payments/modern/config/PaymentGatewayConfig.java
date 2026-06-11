package com.fintech.payments.modern.config;

import io.micrometer.observation.ObservationRegistry;
import io.micrometer.observation.aop.ObservedAspect;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.reactive.function.client.WebClient;

@Configuration
public class PaymentGatewayConfig {

    @Value("${payments.acquirer.url}")
    private String acquirerUrl;

    @Bean("acquirerWebClient")
    public WebClient acquirerWebClient(WebClient.Builder builder) {
        return builder.baseUrl(acquirerUrl).build();
    }

    // Enables @Observed spans on service methods
    @Bean
    public ObservedAspect observedAspect(ObservationRegistry observationRegistry) {
        return new ObservedAspect(observationRegistry);
    }
}
