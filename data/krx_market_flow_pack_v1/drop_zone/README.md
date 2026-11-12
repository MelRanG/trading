# KRX_MARKET_FLOW_PACK_V1 manual drop zone

공식 KRX Data Marketplace 화면의 CSV 다운로드만 저장한다. 파일 이름과
필터는 `runtime/krx_market_flow_pack_v1/human_download_requirements.csv`를
따른다. 원본 CSV를 수정하지 않는다.

각 CSV 옆에는 `<filename>.metadata.json` sidecar가 필요하다. 필수 예시는:

```json
{
  "source_dataset_id": "KOSPI_INVESTOR_TRADING",
  "retrieved_at_utc": "2026-08-07T00:00:00+00:00",
  "observation_date_column": "일자",
  "instrument_or_market": "KOSPI",
  "investor_type_column": "투자자구분",
  "metrics": [
    {"column": "순매수거래대금", "metric_name": "net_buy_value", "unit": "KRW"}
  ]
}
```

실제 다운로드 스키마를 확인한 뒤에만 column mapping을 기록한다. 추측한
필드명은 사용하지 않는다.

