from lead_collector.services.enrichment.bulk import MAX_BULK_HOTELS, enrich_hotels_bulk


def _already_enriched(hotel):
    return (
        bool(hotel.get('enrichment_status'))
        and isinstance(hotel.get('business_emails'), list)
        and isinstance(hotel.get('business_phones'), list)
        and isinstance(hotel.get('social_profiles'), dict)
        and isinstance(hotel.get('decision_makers'), list)
    )


def _merge_result(hotel, result):
    if result.get('status') == 'ERROR':
        return {**hotel, 'enrichment_status': 'ERROR'}
    return {
        **hotel,
        **(result.get('hotel') or {}),
        'enrichment_status': result.get('status'),
        'enrichment_sources': result.get('sources') or hotel.get('enrichment_sources') or {},
        'website_confidence': result.get('website_confidence'),
        'business_emails': result.get('business_emails') or [],
        'business_phones': result.get('business_phones') or [],
        'whatsapp_contacts': result.get('whatsapp_contacts') or [],
        'social_profiles': result.get('social_profiles') or {},
        'social_profile_sources': result.get('social_profile_sources') or {},
        'discovered_pages': result.get('discovered_pages') or {},
        'decision_makers': result.get('decision_makers') or [],
    }


def prepare_hotels_for_export(hotels):
    """Enrich export rows through bounded free Official Website batches only."""
    prepared = [dict(hotel) for hotel in hotels]
    pending = [
        (index, hotel) for index, hotel in enumerate(prepared)
        if hotel.get('name') and hotel.get('website') and not _already_enriched(hotel)
    ]
    for offset in range(0, len(pending), MAX_BULK_HOTELS):
        batch = pending[offset:offset + MAX_BULK_HOTELS]
        response = enrich_hotels_bulk([hotel for _, hotel in batch])
        for (index, hotel), result in zip(batch, response['results']):
            prepared[index] = _merge_result(hotel, result)
    return prepared
