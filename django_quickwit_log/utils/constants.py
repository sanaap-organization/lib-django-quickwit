default_index_config = {
    "version": "0.6",
    "doc_mapping": {
        "timestamp_field": "timestamp",
        "field_mappings": [
            {
                "name": "timestamp",
                "type": "datetime",
                "input_formats": ["unix_timestamp", "iso8601"],
                "fast": True
            },
            {
                "name": "level",
                "type": "text",
                "tokenizer": "raw",
                "fast": True
            },
            {
                "name": "logger",
                "type": "text",
                "tokenizer": "raw",
                "fast": True
            },
            {
                "name": "message",
                "type": "text",
                "tokenizer": "default"
            },
            {
                "name": "module",
                "type": "text",
                "tokenizer": "raw"
            },
            {
                "name": "function",
                "type": "text",
                "tokenizer": "raw"
            },
            {
                "name": "line",
                "type": "u64"
            },
            {
                "name": "app_name",
                "type": "text",
                "tokenizer": "raw",
                "fast": True
            }
        ]
    },
    "search_settings": {
        "default_search_fields": ["message", "logger", "module"]
    },
    "indexing_settings": {
        "commit_timeout_secs": 1
    },
    "retention": {"period": "30d"}
}