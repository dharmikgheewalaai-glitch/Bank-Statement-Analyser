LAYOUTS = {
    "format_1": {
        "name": "Bank Statement Format 1",
        "groups": [
            ["serial no","sr no","sr. no.","sr."], ["transaction date"], ["value date"],
            ["description"], ["cheque number","cheque no"], ["debit"], ["credit"], ["balance"]
        ],
    },
    "format_2": {
        "name": "Bank Statement Format 2",
        "groups": [
            ["value date"], ["post date"], ["details"], ["cheque number","cheque no"],
            ["debit"], ["credit"], ["balance"]
        ],
    },
    "format_3": {
        "name": "Bank Statement Format 3",
        "groups": [
            ["date"], ["narration"], ["chq./ref.no.","chq/ref/no","chq ref no"],
            ["value dt","value date"], ["withdrawal amt."], ["deposit amt."], ["closing balance"]
        ],
    },
    "format_4": {
        "name": "Bank Statement Format 4",
        "groups": [
            ["date"], ["value date"], ["particulars"], ["tran type"], ["tran id"],
            ["cheque details"], ["withdrawals"], ["deposits"], ["balance"], ["dr/cr"]
        ],
    },
    "format_5": {
        "name": "Bank Statement Format 5",
        "groups": [["date"], ["transaction id"], ["remarks"],
                   ["amount(dr/cr)","amount (dr/cr)"], ["balance(dr/cr)","balance (dr/cr)"]]
    },
    "format_6": {
        "name": "Bank Statement Format 6",
        "groups": [["date"], ["instrument id"], ["amount(dr/cr)","amount (dr/cr)"],
                   ["type(dr/cr)","type (dr/cr)"], ["balance(dr/cr)","balance (dr/cr)"], ["remark"]]
    },
    "format_7": {
        "name": "Bank Statement Format 7",
        "groups": [
            ["sr. no.","sr no","serial no"], ["valuedate","value date"], ["transaction date"],
            ["particulars"], ["chq./ref. number","chq/ref number"], ["debit"], ["credit"], ["closing balance"]
        ],
    },
}

ALIASES = {
    "date": ["transaction date","post date","date","value date","valuedate"],
    "particulars": ["description","details","narration","particulars","remarks","remark"],
    "debit": ["debit","withdrawal amt.","withdrawals","amount(dr)","amount (dr)","amount dr"],
    "credit": ["credit","deposit amt.","deposits","amount(cr)","amount (cr)","amount cr"],
    "balance": ["balance","closing balance","balance(dr/cr)","balance (dr/cr)"],
    "amount_drcr": ["amount(dr/cr)","amount (dr/cr)"],
}
