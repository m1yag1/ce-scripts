#!/usr/bin/env bash

set -euo pipefail

: "${GITHUB_TOKEN:?}"
: "${ABL_RAW_URL:?}"
: "${CORGI_URL:=https://corgi-staging.ce.openstax.org}"

# shellcheck disable=SC2016
gh_abl_to_corgi_abl='[
    .approved_books|.[]|
        (.platforms|.[0]) as $platform|
        .repository_name as $repository_name|
        .versions|.[]|
            .min_code_version as $code_version|
            .commit_sha as $sha|
            .commit_metadata|
                .committed_at as $committed_at|
                .books|.[]|
                    {
                        repository_name: $repository_name,
                        code_version: $code_version,
                        uuid: .uuid,
                        slug: .slug,
                        committed_at: $committed_at,
                        consumer: $platform,
                        commit_sha: $sha,
                    }
] |
group_by(.uuid)|.[]|
sort_by(.committed_at)|.[-1]|
select(.consumer == "REX")
'
data="$(curl -sSL "$ABL_RAW_URL")"

entries="$(echo "$data" | jq -c "$gh_abl_to_corgi_abl")"

cookie_file="./cookies.txt"

{
    echo "Logging in..." >&2
    curl -sSL --cookie-jar "$cookie_file" -H "Authorization: Bearer $GITHUB_TOKEN" "$CORGI_URL/api/auth/token-login"
    echo "Sending new ABL data..." >&2
    curl -sSL --json "$(echo "$entries" | jq -sc)" -b "$cookie_file" "$CORGI_URL/api/abl/"
    echo "Done!" >&2
}
