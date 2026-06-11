package com.fintech.fx.legacy;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.scheduling.annotation.EnableScheduling;

@SpringBootApplication
@EnableScheduling
public class FxSettlementApplication {

    public static void main(String[] args) {
        SpringApplication.run(FxSettlementApplication.class, args);
    }
}
