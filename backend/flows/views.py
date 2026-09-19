from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from organizations.permissions import can_manage_settings, get_current_membership
from .models import CustomerFlow, FlowLog, FlowRun
from .serializers import CustomerFlowSerializer, FlowLogSerializer, FlowRunSerializer
from .services import cancel_flow_run, restart_flow_run


class FlowListCreateView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        membership = get_current_membership(request.user)
        if not can_manage_settings(membership): return Response({"detail": "Only owners and admins can manage flows."}, status=403)
        return Response(CustomerFlowSerializer(CustomerFlow.objects.filter(organization=membership.organization), many=True).data)
    def post(self, request):
        membership = get_current_membership(request.user)
        if not can_manage_settings(membership): return Response({"detail": "Only owners and admins can manage flows."}, status=403)
        serializer = CustomerFlowSerializer(data=request.data); serializer.is_valid(raise_exception=True)
        flow = serializer.save(organization=membership.organization, created_by=request.user)
        return Response(CustomerFlowSerializer(flow).data, status=status.HTTP_201_CREATED)


class FlowDetailView(APIView):
    permission_classes = [IsAuthenticated]
    def get_object(self, request, pk):
        membership = get_current_membership(request.user)
        if not can_manage_settings(membership): return None
        return CustomerFlow.objects.filter(id=pk, organization=membership.organization).first()
    def get(self, request, pk):
        flow = self.get_object(request, pk)
        return Response(CustomerFlowSerializer(flow).data) if flow else Response({"detail": "Flow not found."}, status=404)
    def patch(self, request, pk):
        flow = self.get_object(request, pk)
        if not flow: return Response({"detail": "Flow not found."}, status=404)
        serializer = CustomerFlowSerializer(flow, data=request.data, partial=True); serializer.is_valid(raise_exception=True); serializer.save()
        return Response(serializer.data)
    def delete(self, request, pk):
        flow = self.get_object(request, pk)
        if not flow: return Response({"detail": "Flow not found."}, status=404)
        flow.delete(); return Response(status=204)


class FlowRunListView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        membership = get_current_membership(request.user)
        if not can_manage_settings(membership): return Response({"detail": "Only owners and admins can view flow runs."}, status=403)
        runs = FlowRun.objects.select_related("flow", "contact").filter(organization=membership.organization)[:100]
        return Response(FlowRunSerializer(runs, many=True).data)


class FlowRunCancelView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        membership = get_current_membership(request.user)
        if not can_manage_settings(membership):
            return Response({"detail": "Only owners and admins can cancel flow runs."}, status=403)
        run = cancel_flow_run(pk, membership.organization)
        if run is None:
            return Response({"detail": "Flow run not found."}, status=404)
        return Response(FlowRunSerializer(run).data)


class FlowRunRestartView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        membership = get_current_membership(request.user)
        if not can_manage_settings(membership):
            return Response({"detail": "Only owners and admins can restart flow runs."}, status=403)
        previous_run, new_run = restart_flow_run(pk, membership.organization)
        if previous_run is None:
            return Response({"detail": "Flow run not found."}, status=404)
        if new_run is None:
            return Response({"detail": "A different active run already exists for this flow and contact."}, status=409)
        return Response(
            {"previous_run": FlowRunSerializer(previous_run).data, "run": FlowRunSerializer(new_run).data},
            status=status.HTTP_201_CREATED,
        )


class FlowLogListView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        membership = get_current_membership(request.user)
        if not can_manage_settings(membership): return Response({"detail": "Only owners and admins can view flow logs."}, status=403)
        logs = FlowLog.objects.filter(organization=membership.organization)
        if request.query_params.get("run"): logs = logs.filter(run_id=request.query_params["run"])
        return Response(FlowLogSerializer(logs[:200], many=True).data)
