package com.fintech.ledger.legacy.batch;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

import java.util.concurrent.atomic.AtomicBoolean;

/**
 * LEGACY — End-of-day reconciliation batch.
 *
 * PROBLEM: in-JVM @Scheduled batch — runs on every instance simultaneously
 *          (no distributed lock); horizontal scaling double-runs the EOD.
 * PROBLEM: Thread.sleep polling loop holds a scheduler thread for the whole
 *          settlement window.
 * PROBLEM: state in an AtomicBoolean — a crash mid-run loses progress; the
 *          job is not resumable.
 *
 * MIGRATE TO: event-driven settlement (EventBridge schedule → ECS task /
 * Step Functions) with checkpointed state — see
 * fintech-java-spring2-to-spring3 Step 6.
 */
@Component
public class EndOfDayBatchJob {

    private static final Logger log = LoggerFactory.getLogger(EndOfDayBatchJob.class);

    private final AtomicBoolean running = new AtomicBoolean(false);

    @Scheduled(cron = "${ledger.eod.cron:0 0 22 * * *}")
    public void runEndOfDay() {
        if (!running.compareAndSet(false, true)) {
            log.warn("EOD already running — skipping");
            return;
        }
        try {
            log.info("EOD reconciliation started");
            // PROBLEM: poll-and-sleep until upstream files arrive
            for (int attempt = 0; attempt < 60; attempt++) {
                if (settlementFilesArrived()) {
                    log.info("Settlement files present after {} polls — reconciling", attempt);
                    return;
                }
                try {
                    Thread.sleep(60_000); // blocks a scheduler thread for up to an hour
                } catch (InterruptedException e) {
                    Thread.currentThread().interrupt();
                    return;
                }
            }
            log.error("EOD gave up waiting for settlement files");
        } finally {
            running.set(false);
        }
    }

    private boolean settlementFilesArrived() {
        // Stub — in the real system this polled an SFTP drop directory
        return false;
    }
}
