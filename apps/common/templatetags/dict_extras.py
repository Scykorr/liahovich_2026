from django.template import Library

from apps.common.labels import format_centers, human_label, join_feature_labels, ru_clusters as cluster_phrase

register = Library()


@register.filter
def get_item(mapping, key):
    if mapping is None:
        return ""
    return mapping.get(key, "")


@register.filter
def ru_label(value) -> str:
    return human_label(str(value) if value is not None else "")


@register.filter
def ru_features(values) -> str:
    return join_feature_labels(values)


@register.filter
def ru_centers(centers) -> str:
    return format_centers(centers)


@register.filter
def ru_clusters(value) -> str:
    return cluster_phrase(value)
