#!/bin/bash
VM_SKU=$(curl --connect-timeout 10 -s -H Metadata:true "http://169.254.169.254/metadata/instance?api-version=2018-04-02" | jq '.compute.vmSize')
VM_SKU="${VM_SKU%\"}"
VM_SKU="${VM_SKU#\"}"

host=$(hostname)

echo "VM SKU: $VM_SKU"
if [[ $VM_SKU == "Standard_HB120rs_v2" ]]; then
    value=`/data/node_utils/Stream/stream_zen_double 400000000 0 1,5,9,13,17,21,25,29,33,37,41,45,49,53,57,61,65,69,73,77,81,85,89,93,97,101,105,109,113,117 | grep Triad: | awk '{print $2}'`
    value_int=${value%.*}
    if (($value_int < 280000)); then
        echo "$host : $value_int MB/s Failed <------------------ Too low"
        exit -1
    else
        echo "$host : $value_int MB/s Passed"
    fi
elif [[ $VM_SKU == "Standard_HB60rs" ]]; then
    value=`/data/node_utils/Stream/stream_zen_double 400000000 0 1,5,9,13,17,21,25,29,33,37,41,45,49,53,57 | grep Triad: | awk '{print $2}'`
    value_int=${value%.*}
    if (($value_int < 240000)); then
        echo "$host : $value_int MB/s Failed <------------------ Too low"
        exit -1
    else
        echo "$host : $value_int MB/s Passed"
    fi
elif  [[ $VM_SKU == "Standard_HC44rs" ]]; then
    value=`/data/node_utils/Stream/stream_zen_double 400000000 0 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,23,24,25,26,27,28,29,30,31,32,33,34,35,36,37,38 | grep Triad: | awk '{print $2}'`
    value_int=${value%.*}
    if (($value_int < 190000)); then
        echo "$host : $value_int MB/s Failed <------------------ Too low"
        exit -1
    else
        echo "$host : $value_int MB/s Passed"
    fi
else
    echo "$host : $VM_SKU has no defined stream test"
fi
