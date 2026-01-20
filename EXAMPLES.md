# Example question

## 2-Service Combinations

- BAG + CBS:
```jsonl
{  "question": "What is the population density around the office building at Damrak 1 in Amsterdam?"  }
{  "question": "What's the average income in the area where Utrecht's 1636 education building is located?"  }
```

- BAG + Rijkswaterstaat:
```jsonl
{  "question": "What is the water level near the building at Coolsingel 40 in Rotterdam?"  }
{  "question": "Is there a bridge or tunnel near the Damrak address in Amsterdam?"  }
```

- CBS + Rijkswaterstaat:
```jsonl
{  "question": "Which city has the highest unemployment rate and worst road conditions?"  }
{  "question": "Compare the population density with water levels across Amsterdam, Utrecht, and Rotterdam"  }
```

- BAG + BRT:
```jsonl
{  "question": "What parks are near the historic building on Oudegracht in Utrecht?"  }
{  "question": "Which water board is responsible for the area where Damrak 1 is located?"  }
```

- CBS + BRT:
```jsonl
{  "question": "Which safety region covers the area with the lowest unemployment?"  }
{  "question": "How much park space per capita does Amsterdam have?" }
```
(CBS population + BRT landscape)

- BGT + Rijkswaterstaat:
```jsonl
{  "question": "Compare the canal width (BGT) with water levels (RWS) for Amsterdam's waterways"  }
```

## 3+ Service Combinations

- BAG + CBS + Rijkswaterstaat:
```jsonl
{  "question": "For the Erasmusbrug area in Rotterdam, what's the building type, population statistics, and water level?"  }
```

- CBS + BRT + Rijkswaterstaat:
```
{  "question": "Which province has the most infrastructure managed by Rijkswaterstaat and the highest population density?"  }
```

- BAG + BGT + BRT:
```jsonl
{  "question": "What's the full picture of the Damrak area: building purpose, road surface types, and neighborhood names?"  }
```

## Comprehensive (4-5 services)
```jsonl
{  "question": "Give me a complete profile of Amsterdam: building types, demographics, infrastructure status, terrain, parks, and administrative authorities"  }
{  "question": "Compare Rotterdam and Utrecht on: average income, road conditions, park availability, and water management"  }
```
