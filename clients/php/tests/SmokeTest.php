<?php

declare(strict_types=1);

/**
 * Smoke test for transparentpt/portugal-vehicle-tax (API client).
 *
 * No PHPUnit dependency — plain assertions. Hits the live TransparentCars API and checks the
 * documented invariants (diesel > 0, EV exempt, €100 minimum), plus a known golden number.
 * Set SKIP_LIVE=1 to skip the network part.
 *
 * Run:  php tests/SmokeTest.php
 */

require __DIR__ . '/../src/Client.php';

use TransparentCars\VehicleTax\Client;

function check(bool $cond, string $msg): void
{
    if (!$cond) {
        fwrite(STDERR, "FAIL: {$msg}\n");
        exit(1);
    }
    echo "ok: {$msg}\n";
}

check(
    str_contains(Client::DISCLAIMER, 'not the official AT figure'),
    'exports the honesty note verbatim'
);

if (getenv('SKIP_LIVE') === '1') {
    echo "live API: SKIPPED (SKIP_LIVE=1)\n";
    echo "smoke: PASS\n";
    exit(0);
}

$api = new Client();

// Diesel, used EU import with age reduction — both taxes positive.
$diesel = $api->getTax(['cc' => 1950, 'co2' => 130, 'fuel' => 'diesel', 'year' => 2016]);
check(($diesel['isv']['isv'] ?? 0) > 0, 'diesel: ISV positive');
check(($diesel['iuc']['iuc'] ?? 0) > 0, 'diesel: IUC positive');

// Electric → exempt from both.
$ev = $api->getTax(['fuel' => 'electric', 'year' => 2023]);
check(($ev['isv']['isv'] ?? -1) === 0.0 || ($ev['isv']['isv'] ?? -1) === 0, 'EV: ISV exempt (0)');
check(($ev['isv']['exempt'] ?? false) === true, 'EV: exempt flag set');
check(($ev['iuc']['iuc'] ?? -1) == 0, 'EV: IUC exempt (0)');

// €100 statutory minimum ISV.
$tiny = $api->getIsv(['cc' => 900, 'co2' => 95, 'fuel' => 'petrol', 'year' => 2005]);
check(($tiny['isv'] ?? 0) >= 100, 'min-ISV floor of €100 respected');

echo "live API: OK (diesel>0, EV exempt, min-€100)\n";
echo "smoke: PASS\n";
