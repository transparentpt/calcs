<?php

declare(strict_types=1);

namespace TransparentCars\VehicleTax;

/**
 * Client for the TransparentCars Portuguese vehicle-tax API — ISV (import tax) + IUC (annual road tax).
 *
 * This is a thin HTTP client. It does NOT re-implement the tax math — it calls the public,
 * key-free TransparentCars API (https://transparent.pt/api/public/isv), which returns BOTH taxes.
 *
 * The numbers are a maintained estimate, cross-checked against the official AT simulator;
 * not the official AT figure. See https://transparent.pt.
 */
final class Client
{
    /** Verbatim honesty note (marketing-copy-honesty rule). */
    public const DISCLAIMER =
        'A maintained estimate, cross-checked against the official AT simulator; not the official AT figure.';

    private string $baseUrl;
    private int $timeout;

    /**
     * @param string $baseUrl Override to self-host the open-source API.
     * @param int    $timeout Request timeout in seconds.
     */
    public function __construct(string $baseUrl = 'https://transparent.pt/api/public', int $timeout = 8)
    {
        $this->baseUrl = rtrim($baseUrl, '/');
        $this->timeout = $timeout;
    }

    /**
     * ISV + IUC for a vehicle (single API call).
     *
     * @param array<string,scalar|bool|null> $query cc, co2, fuel, year, month, from_eu,
     *        range_km, used, vehicle_type, particulas — all optional.
     * @return array<string,mixed> Decoded response: ['isv'=>[...], 'iuc'=>[...], 'source'=>..., 'disclaimer'=>...]
     * @throws \RuntimeException on transport error or non-200.
     */
    public function getTax(array $query): array
    {
        $params = [];
        foreach ($query as $k => $v) {
            if ($v === null) {
                continue;
            }
            $params[$k] = is_bool($v) ? ($v ? 'true' : 'false') : (string) $v;
        }
        $url = $this->baseUrl . '/isv?' . http_build_query($params);
        $body = $this->httpGet($url);

        /** @var array<string,mixed>|null $data */
        $data = json_decode($body, true);
        if (!is_array($data)) {
            throw new \RuntimeException('TransparentCars API: invalid JSON response.');
        }
        return $data;
    }

    /**
     * Convenience: just the ISV part.
     *
     * @param array<string,scalar|bool|null> $query
     * @return array<string,mixed>
     */
    public function getIsv(array $query): array
    {
        return $this->getTax($query)['isv'] ?? [];
    }

    /**
     * Convenience: just the IUC part.
     *
     * @param array<string,scalar|bool|null> $query
     * @return array<string,mixed>
     */
    public function getIuc(array $query): array
    {
        return $this->getTax($query)['iuc'] ?? [];
    }

    private function httpGet(string $url): string
    {
        if (\function_exists('curl_init')) {
            $ch = curl_init($url);
            curl_setopt_array($ch, [
                CURLOPT_RETURNTRANSFER => true,
                CURLOPT_TIMEOUT        => $this->timeout,
                CURLOPT_HTTPHEADER     => ['Accept: application/json'],
                CURLOPT_USERAGENT      => 'transparentcars-portugal-vehicle-tax-php/1.0',
            ]);
            $body = curl_exec($ch);
            $status = (int) curl_getinfo($ch, CURLINFO_RESPONSE_CODE);
            $err = curl_error($ch);
            curl_close($ch);
            if ($body === false) {
                throw new \RuntimeException("TransparentCars API request failed: {$err}");
            }
            if ($status < 200 || $status >= 300) {
                throw new \RuntimeException("TransparentCars API returned HTTP {$status} for {$url}");
            }
            return (string) $body;
        }

        // Fallback: stream wrapper (allow_url_fopen).
        $ctx = stream_context_create(['http' => [
            'timeout' => $this->timeout,
            'header'  => "Accept: application/json\r\n",
        ]]);
        $body = @file_get_contents($url, false, $ctx);
        if ($body === false) {
            throw new \RuntimeException("TransparentCars API request failed for {$url} (enable cURL or allow_url_fopen).");
        }
        return $body;
    }
}
